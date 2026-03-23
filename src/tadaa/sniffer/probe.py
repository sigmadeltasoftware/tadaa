"""Probe script to find the correct Tado radio configuration.

Tries multiple sync words, data rates, and modulations to find
the combination that produces valid 802.15.4 frames.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from tadaa.cc1101.registers import (
    ConfigReg,
    StatusReg,
    MarcState,
    MOD_GFSK,
    MOD_2FSK,
    XTAL_FREQ_HZ,
    PKTCTRL0_VARIABLE_LENGTH,
    PKTCTRL0_INFINITE_LENGTH,
)
from tadaa.cc1101.config import RadioConfig


# Known sync words used in 6LoWPAN / 802.15.4 / TI designs
SYNC_CANDIDATES = [
    (0x7209, "802.15.4 SUN FSK"),
    (0x0972, "802.15.4 SUN FSK (swapped)"),
    (0x904E, "802.15.4g MR-FSK"),
    (0x4E90, "802.15.4g MR-FSK (swapped)"),
    (0xD391, "CC1101 default"),
    (0x91D3, "CC1101 default (swapped)"),
    (0x632D, "TI common"),
    (0x2D63, "TI common (swapped)"),
    (0x930B, "TI reference"),
    (0x0B93, "TI reference (swapped)"),
    (0x55AA, "alternating pattern"),
    (0xAA55, "alternating pattern (inv)"),
    (0x0000, "no sync (carrier sense)"),
]

RATE_CANDIDATES = [
    (38_400, 20_000, "38.4k / 20k dev"),
    (38_400, 25_000, "38.4k / 25k dev"),
    (50_000, 25_000, "50k / 25k dev"),
    (100_000, 50_000, "100k / 50k dev"),
    (9_600, 5_000, "9.6k / 5k dev"),
    (250_000, 127_000, "250k / 127k dev (802.15.4)"),
]


def is_valid_802154(data: bytes) -> Optional[dict]:
    """Check if data starts with a valid IEEE 802.15.4 frame header.

    Returns parsed info dict or None.
    """
    if len(data) < 3:
        return None

    fc = data[0] | (data[1] << 8)
    frame_type = fc & 0x07
    seq_num = data[2]

    # Frame type must be 0-3
    if frame_type > 3:
        return None

    dst_mode = (fc >> 10) & 0x03
    src_mode = (fc >> 14) & 0x03
    security = (fc >> 3) & 0x01
    ack_req = (fc >> 5) & 0x01
    panid_comp = (fc >> 6) & 0x01

    # Validate addressing modes (1 is reserved)
    if dst_mode == 1 or src_mode == 1:
        return None

    type_names = {0: "Beacon", 1: "Data", 2: "ACK", 3: "CMD"}

    # For ACK frames, there should be no addressing
    if frame_type == 2 and (dst_mode != 0 or src_mode != 0):
        return None

    # For Data/CMD frames, at least one addressing mode should be set
    if frame_type in (1, 3) and dst_mode == 0 and src_mode == 0:
        return None

    return {
        "frame_type": type_names[frame_type],
        "seq_num": seq_num,
        "security": bool(security),
        "ack_req": bool(ack_req),
        "panid_comp": bool(panid_comp),
        "dst_mode": dst_mode,
        "src_mode": src_mode,
        "fc_hex": f"0x{fc:04X}",
    }


def probe(driver, frequency_hz: int = 868_300_000, duration_per_config_s: float = 5.0):
    """Try many radio configs and report which ones produce valid 802.15.4 frames."""

    results = []

    for sync_word, sync_name in SYNC_CANDIDATES:
        for data_rate, deviation, rate_name in RATE_CANDIDATES:
            for mod, mod_name in [(MOD_GFSK, "GFSK"), (MOD_2FSK, "2-FSK")]:
                config = RadioConfig(
                    name=f"probe_{sync_word:04X}_{data_rate}_{mod_name}",
                    frequency_hz=frequency_hz,
                    data_rate_baud=data_rate,
                    modulation=mod,
                    deviation_hz=deviation,
                    sync_word=sync_word,
                    bandwidth_khz=200.0,
                )

                # Configure radio
                driver.set_idle()
                driver.flush_rx()
                driver.set_frequency_hz(frequency_hz)

                driver.write_register(ConfigReg.SYNC1, (sync_word >> 8) & 0xFF)
                driver.write_register(ConfigReg.SYNC0, sync_word & 0xFF)

                drate_m, drate_e = config.calc_data_rate_regs()
                driver.write_register(ConfigReg.MDMCFG4, drate_e & 0x0F)
                driver.write_register(ConfigReg.MDMCFG3, drate_m & 0xFF)

                # Sync mode: if sync_word is 0x0000, use carrier sense only (no sync)
                if sync_word == 0x0000:
                    driver.write_register(ConfigReg.MDMCFG2, mod | 0x00)  # no sync
                else:
                    driver.write_register(ConfigReg.MDMCFG2, mod | 0x02)  # 16/16 sync

                dev_m, dev_e = config.calc_deviation_regs()
                driver.write_register(ConfigReg.DEVIATN, ((dev_e & 0x07) << 4) | (dev_m & 0x07))

                driver.write_register(ConfigReg.PKTCTRL0, PKTCTRL0_VARIABLE_LENGTH)
                driver.write_register(ConfigReg.PKTCTRL1, 0x04)  # append status
                driver.write_register(ConfigReg.PKTLEN, 0xFF)
                driver.write_register(ConfigReg.IOCFG0, 0x06)

                driver.set_rx_mode()

                # Capture for duration
                packets = []
                valid_frames = []
                deadline = time.monotonic() + duration_per_config_s

                while time.monotonic() < deadline:
                    rx_bytes = driver.get_rx_bytes()
                    marcstate = driver.get_marcstate()

                    if marcstate == MarcState.RXFIFO_OVERFLOW:
                        driver.set_idle()
                        driver.flush_rx()
                        driver.set_rx_mode()
                        continue

                    if rx_bytes == 0:
                        time.sleep(0.001)
                        continue

                    length_raw = driver.read_rx_fifo(1)
                    if not length_raw or length_raw[0] == 0:
                        continue

                    payload_len = length_raw[0]
                    total = payload_len + 2
                    data = driver.read_rx_fifo(total)
                    if len(data) < total:
                        continue

                    payload = data[:payload_len]
                    rssi_raw = data[payload_len]
                    rssi_dbm = driver.rssi_to_dbm(rssi_raw)

                    packets.append(payload)

                    # Check if it's valid 802.15.4
                    parsed = is_valid_802154(payload)
                    if parsed:
                        valid_frames.append({
                            "parsed": parsed,
                            "rssi_dbm": rssi_dbm,
                            "hex": " ".join(f"{b:02X}" for b in payload),
                            "length": len(payload),
                        })

                driver.set_idle()

                if packets:
                    entry = {
                        "sync_word": f"0x{sync_word:04X}",
                        "sync_name": sync_name,
                        "data_rate": data_rate,
                        "deviation": deviation,
                        "modulation": mod_name,
                        "total_packets": len(packets),
                        "valid_802154": len(valid_frames),
                        "frames": valid_frames[:5],  # first 5 for inspection
                    }
                    results.append(entry)

                    status = "VALID 802.15.4!" if valid_frames else "no valid frames"
                    print(
                        f"  sync={sync_word:04X} rate={data_rate:>6} {mod_name:<5} "
                        f"=> {len(packets):>3} pkts, {len(valid_frames):>3} valid "
                        f"[{status}]"
                    )

    return results
