"""Packet capture for the CC1101 radio."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from tadaa.cc1101.config import RadioConfig
from tadaa.cc1101.registers import (
    ConfigReg,
    StatusReg,
    MarcState,
    PKTCTRL0_VARIABLE_LENGTH,
)


@dataclass
class CapturedPacket:
    """A single captured over-the-air packet."""

    timestamp: float
    raw: bytes
    rssi_dbm: float
    lqi: int

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    def hex_dump(self) -> str:
        """Return *raw* bytes as an uppercase space-separated hex string."""
        return " ".join(f"{b:02X}" for b in self.raw)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "timestamp": self.timestamp,
            "hex": self.hex_dump(),
            "rssi_dbm": self.rssi_dbm,
            "lqi": self.lqi,
            "length": len(self.raw),
        }


class PacketCapture:
    """Configure the CC1101 and capture incoming packets into a buffer.

    Parameters
    ----------
    driver:
        A :class:`~tadaa.cc1101.driver.CC1101Driver` instance.
    config:
        Radio configuration describing frequency, modulation, etc.
    """

    #: IOCFG0 value: GDO0 asserts when a sync word is received and de-asserts
    #: when the packet is received (CRC OK) or RX FIFO overflows.
    _IOCFG0_SYNC = 0x06

    #: PKTCTRL1 value: append two status bytes (RSSI + LQI/CRC) after payload.
    _PKTCTRL1_APPEND_STATUS = 0x04

    #: Maximum packet length register value (variable-length mode ceiling).
    _PKTLEN_MAX = 0xFF

    def __init__(self, driver, config: RadioConfig) -> None:
        self._driver = driver
        self._config = config
        self.buffer: List[CapturedPacket] = []

    # ------------------------------------------------------------------
    # Radio setup
    # ------------------------------------------------------------------

    def configure_radio(self) -> None:
        """Write CC1101 registers to match *self._config*.

        Writes in order:
        - FREQ2/FREQ1/FREQ0 — carrier frequency
        - SYNC1/SYNC0 — sync word
        - MDMCFG4/MDMCFG3 — data-rate exponent/mantissa
        - MDMCFG2 — modulation format, sync-word qualifier
        - DEVIATN — frequency deviation
        - PKTCTRL0 — variable-length packets
        - PKTCTRL1 — append status bytes
        - PKTLEN — maximum packet length
        - IOCFG0 — GDO0 signal configuration
        """
        driver = self._driver
        cfg = self._config

        # Frequency
        driver.set_frequency_hz(cfg.frequency_hz)

        # Sync word (big-endian 16-bit: high byte → SYNC1, low byte → SYNC0)
        driver.write_register(ConfigReg.SYNC1, (cfg.sync_word >> 8) & 0xFF)
        driver.write_register(ConfigReg.SYNC0, cfg.sync_word & 0xFF)

        # Data rate
        drate_m, drate_e = cfg.calc_data_rate_regs()
        # MDMCFG4: upper nibble = channel bandwidth (leave 0 for now), lower nibble = DRATE_E
        driver.write_register(ConfigReg.MDMCFG4, drate_e & 0x0F)
        driver.write_register(ConfigReg.MDMCFG3, drate_m & 0xFF)

        # Modulation: set mod format bits, enable 16/16 sync word qualifier
        driver.write_register(ConfigReg.MDMCFG2, cfg.modulation | 0x02)

        # Deviation
        dev_m, dev_e = cfg.calc_deviation_regs()
        driver.write_register(ConfigReg.DEVIATN, ((dev_e & 0x07) << 4) | (dev_m & 0x07))

        # Packet format: variable length, no whitening
        driver.write_register(ConfigReg.PKTCTRL0, PKTCTRL0_VARIABLE_LENGTH)

        # Packet control: append status bytes (RSSI, LQI/CRC)
        driver.write_register(ConfigReg.PKTCTRL1, self._PKTCTRL1_APPEND_STATUS)

        # Maximum packet length
        driver.write_register(ConfigReg.PKTLEN, self._PKTLEN_MAX)

        # GDO0: active when sync word received
        driver.write_register(ConfigReg.IOCFG0, self._IOCFG0_SYNC)

    # ------------------------------------------------------------------
    # Packet reception
    # ------------------------------------------------------------------

    def receive_packet(self, timeout_s: float = 1.0) -> Optional[CapturedPacket]:
        """Block until a packet is received or *timeout_s* elapses.

        Handles RX FIFO overflow by flushing and re-entering RX mode.

        Parameters
        ----------
        timeout_s:
            Maximum time to wait for a packet (seconds).

        Returns
        -------
        CapturedPacket or None
            The captured packet, or *None* on timeout or parse error.
        """
        driver = self._driver
        deadline = time.monotonic() + timeout_s

        while time.monotonic() < deadline:
            rx_bytes = driver.get_rx_bytes()

            # Check for FIFO overflow
            marcstate = driver.get_marcstate()
            if marcstate == MarcState.RXFIFO_OVERFLOW:
                driver.set_idle()
                driver.flush_rx()
                driver.set_rx_mode()
                continue

            if rx_bytes == 0:
                time.sleep(0.001)
                continue

            # First byte in variable-length mode is the length field
            length_raw = driver.read_rx_fifo(1)
            if not length_raw:
                continue

            payload_len = length_raw[0]
            if payload_len == 0:
                continue

            # Read payload + 2 appended status bytes (RSSI, LQI/CRC_OK)
            total = payload_len + 2
            data = driver.read_rx_fifo(total)
            if len(data) < total:
                continue

            payload = data[:payload_len]
            rssi_raw = data[payload_len]
            lqi_raw = data[payload_len + 1]

            rssi_dbm = driver.rssi_to_dbm(rssi_raw)
            lqi = lqi_raw & 0x7F  # CRC_OK is bit 7

            return CapturedPacket(
                timestamp=time.time(),
                raw=payload,
                rssi_dbm=rssi_dbm,
                lqi=lqi,
            )

        return None

    # ------------------------------------------------------------------
    # Capture loop
    # ------------------------------------------------------------------

    def run(
        self,
        duration_s: float = 60.0,
        log_path: Optional[Path] = None,
    ) -> List[CapturedPacket]:
        """Capture packets for *duration_s* seconds.

        Configures the radio, enters RX mode, and captures until the
        time budget is exhausted.  Optionally writes a JSON-lines log to
        *log_path*.

        Parameters
        ----------
        duration_s:
            How long to capture (seconds).
        log_path:
            If given, each packet is appended as a JSON line to this file.

        Returns
        -------
        list[CapturedPacket]
            All packets captured during the session.
        """
        self.configure_radio()
        self._driver.set_rx_mode()

        log_file = None
        if log_path is not None:
            log_file = open(log_path, "a", encoding="utf-8")

        try:
            deadline = time.monotonic() + duration_s
            while time.monotonic() < deadline:
                remaining = deadline - time.monotonic()
                pkt = self.receive_packet(timeout_s=min(remaining, 1.0))
                if pkt is not None:
                    self.buffer.append(pkt)
                    if log_file is not None:
                        log_file.write(json.dumps(pkt.to_dict()) + "\n")
                        log_file.flush()
        finally:
            if log_file is not None:
                log_file.close()
            self._driver.set_idle()

        return self.buffer

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_capture(self, path: Path) -> None:
        """Write all buffered packets to *path* as a JSON array.

        Parameters
        ----------
        path:
            Destination file path.
        """
        with open(path, "w", encoding="utf-8") as fh:
            json.dump([pkt.to_dict() for pkt in self.buffer], fh, indent=2)
