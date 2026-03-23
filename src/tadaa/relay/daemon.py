"""Relay daemon: receives packets via CC1101, deduplicates, and retransmits."""

from __future__ import annotations

import random
import time
import logging
import threading
from dataclasses import dataclass, field

from tadaa.cc1101.driver import CC1101Driver
from tadaa.cc1101.config import RadioConfig, SCAN_CONFIGS
from tadaa.cc1101.registers import (
    ConfigReg,
    Strobe,
    MarcState,
    PKTCTRL0_VARIABLE_LENGTH,
)
from tadaa.relay.dedup import DeduplicationBuffer
from tadaa.packets.ieee802154 import parse_mac_frame

log = logging.getLogger(__name__)

# Alias so the rest of the file can use the friendly name from the spec comment.
MARCSTATE_RXFIFO_OVERFLOW = MarcState.RXFIFO_OVERFLOW


@dataclass
class RelayStats:
    packets_relayed: int = 0
    packets_dropped: int = 0
    errors: int = 0
    last_rssi: float = 0.0
    start_time: float = field(default_factory=time.monotonic)
    known_devices: set[str] = field(default_factory=set)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def to_dict(self) -> dict:
        with self._lock:
            uptime = time.monotonic() - self.start_time
            hours = int(uptime // 3600)
            minutes = int((uptime % 3600) // 60)
            seconds = int(uptime % 60)
            return {
                "uptime": f"{hours}h {minutes}m {seconds}s",
                "uptime_seconds": int(uptime),
                "packets_relayed": self.packets_relayed,
                "packets_dropped": self.packets_dropped,
                "last_packet_rssi": self.last_rssi,
                "known_devices": sorted(self.known_devices),
                "errors": self.errors,
            }


class RelayDaemon:
    """Receive-deduplicate-retransmit daemon for CC1101.

    Args:
        driver:       Initialised CC1101Driver instance.
        config:       RadioConfig to program the chip with (defaults to the
                      primary Tado GFSK preset).
        dedup_ttl_s:  Deduplication window in seconds.
    """

    JITTER_MIN_S = 0.005
    JITTER_MAX_S = 0.010

    def __init__(
        self,
        driver: CC1101Driver,
        config: RadioConfig | None = None,
        dedup_ttl_s: float = 5.0,
    ) -> None:
        self._driver = driver
        self._config = config or SCAN_CONFIGS[0]
        self._dedup = DeduplicationBuffer(ttl_seconds=dedup_ttl_s)
        self.stats = RelayStats()
        self._running = False

    # ------------------------------------------------------------------
    # Core processing
    # ------------------------------------------------------------------

    def process_packet(self, raw: bytes, rssi_dbm: float) -> bool:
        """Process one received packet.

        Extracts known device addresses from the MAC frame (best-effort),
        checks for duplicates, applies jitter, writes the packet into the
        TX FIFO, strobes STX, waits for the transmission to complete, and
        returns to RX mode.

        Args:
            raw:      Raw MAC frame bytes.
            rssi_dbm: RSSI of the received packet in dBm.

        Returns:
            True if the packet was relayed, False if it was a duplicate.
        """
        # Track device addresses regardless of dedup decision.
        self._track_devices(raw)

        self.stats.last_rssi = rssi_dbm

        if self._dedup.is_duplicate(raw):
            self.stats.packets_dropped += 1
            log.debug("Dropped duplicate packet (%d bytes)", len(raw))
            return False

        # Jitter to reduce collision risk with the original transmitter.
        jitter = random.uniform(self.JITTER_MIN_S, self.JITTER_MAX_S)
        time.sleep(jitter)

        # Build payload: length byte followed by raw frame.
        payload = bytes([len(raw)]) + raw
        self._driver.write_tx_fifo(payload)
        self._driver.strobe(Strobe.STX)

        # Wait for TX to complete (chip transitions back to IDLE/RX).
        self._wait_tx_complete()

        # Return to receive mode.
        self._driver.strobe(Strobe.SRX)

        self.stats.packets_relayed += 1
        log.info("Relayed %d-byte packet (RSSI=%.1f dBm)", len(raw), rssi_dbm)
        return True

    # ------------------------------------------------------------------
    # Radio configuration
    # ------------------------------------------------------------------

    def configure_radio(self) -> None:
        """Program CC1101 registers for the chosen RadioConfig."""
        drv = self._driver
        cfg = self._config

        drv.reset()

        # Packet format: variable length, no whitening.
        drv.write_register(ConfigReg.PKTCTRL0, PKTCTRL0_VARIABLE_LENGTH)

        # Frequency.
        drv.set_frequency_hz(cfg.frequency_hz)

        # Data rate.
        drate_m, drate_e = cfg.calc_data_rate_regs()
        drv.write_register(ConfigReg.MDMCFG3, drate_m)
        # Preserve upper nibble (channel filter BW) — set to 0 for defaults.
        drv.write_register(ConfigReg.MDMCFG4, drate_e & 0x0F)

        # Modulation.
        drv.write_register(ConfigReg.MDMCFG2, cfg.modulation)

        # Deviation.
        dev_m, dev_e = cfg.calc_deviation_regs()
        drv.write_register(ConfigReg.DEVIATN, (dev_e << 4) | dev_m)

        # Sync word.
        drv.write_register(ConfigReg.SYNC1, (cfg.sync_word >> 8) & 0xFF)
        drv.write_register(ConfigReg.SYNC0, cfg.sync_word & 0xFF)

        log.info("Radio configured: %s @ %.3f MHz", cfg.name, cfg.frequency_hz / 1e6)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Block forever, relaying packets as they arrive.

        Call ``stop()`` from another thread to terminate cleanly.
        """
        self.configure_radio()
        self._driver.strobe(Strobe.SRX)
        self._running = True
        log.info("RelayDaemon started")

        try:
            while self._running:
                try:
                    self._rx_loop_tick()
                except Exception as exc:  # noqa: BLE001
                    self.stats.errors += 1
                    log.error("Error in RX loop: %s", exc)
        finally:
            self._driver.strobe(Strobe.SIDLE)
            log.info("RelayDaemon stopped")

    def stop(self) -> None:
        """Signal the run loop to exit."""
        self._running = False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _rx_loop_tick(self) -> None:
        """Single iteration of the receive loop."""
        drv = self._driver

        # Check for RXFIFO overflow.
        marcstate = drv.get_marcstate()
        if marcstate == MARCSTATE_RXFIFO_OVERFLOW:
            log.warning("RX FIFO overflow — flushing")
            drv.strobe(Strobe.SIDLE)
            drv.strobe(Strobe.SFRX)
            drv.strobe(Strobe.SRX)
            return

        rx_bytes = drv.get_rx_bytes()
        if rx_bytes == 0:
            time.sleep(0.001)
            return

        # Read length byte.
        length_buf = drv.read_rx_fifo(1)
        if not length_buf:
            return
        pkt_len = length_buf[0]

        # Read packet + 2 status bytes (RSSI + LQI/CRC).
        if pkt_len == 0:
            return
        raw_plus_status = drv.read_rx_fifo(pkt_len + 2)
        raw = raw_plus_status[:pkt_len]
        rssi_raw = raw_plus_status[pkt_len] if len(raw_plus_status) > pkt_len else 0
        rssi_dbm = CC1101Driver.rssi_to_dbm(rssi_raw)

        self.process_packet(raw, rssi_dbm)

    def _wait_tx_complete(self, timeout_s: float = 0.1) -> None:
        """Poll MARCSTATE until the chip leaves TX state or timeout expires."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            marcstate = self._driver.get_marcstate()
            if marcstate not in (MarcState.TX, MarcState.FSTXON):
                return
            time.sleep(0.001)

    def _track_devices(self, raw: bytes) -> None:
        """Extract src/dest addresses from a MAC frame and record them."""
        try:
            frame = parse_mac_frame(raw)
        except (ValueError, Exception):
            return

        with self.stats._lock:
            if frame.src_addr is not None:
                addr = frame.src_addr.hex()
                self.stats.known_devices.add(addr)
            if frame.dest_addr is not None:
                addr = frame.dest_addr.hex()
                self.stats.known_devices.add(addr)
