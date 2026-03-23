import time
import pytest
from tadaa.sniffer.capture import CapturedPacket, PacketCapture
from tadaa.cc1101.driver import CC1101Driver
from tadaa.cc1101.config import RadioConfig, MOD_GFSK


def test_captured_packet_fields():
    pkt = CapturedPacket(
        timestamp=1234567890.0,
        raw=b"\x41\x88\x05\x34\x12\x01\x00\x02\x00\xAA",
        rssi_dbm=-72.0,
        lqi=0x3F,
    )
    assert len(pkt.raw) == 10
    assert pkt.rssi_dbm == -72.0


def test_packet_capture_stores_packets(fake_spi):
    driver = CC1101Driver(spi=fake_spi)
    config = RadioConfig(
        name="test",
        frequency_hz=868_000_000,
        data_rate_baud=38400,
        modulation=MOD_GFSK,
        deviation_hz=20_000,
        sync_word=0xD391,
        bandwidth_khz=100,
    )
    capture = PacketCapture(driver, config)
    pkt = CapturedPacket(
        timestamp=time.time(),
        raw=b"\x41\x88\x05\x34\x12\x01\x00\x02\x00\xAA",
        rssi_dbm=-72.0,
        lqi=0x3F,
    )
    capture.buffer.append(pkt)
    assert len(capture.buffer) == 1
    assert capture.buffer[0].rssi_dbm == -72.0


def test_captured_packet_hex_dump():
    pkt = CapturedPacket(
        timestamp=0.0,
        raw=b"\xAA\xBB\xCC",
        rssi_dbm=-80.0,
        lqi=0x20,
    )
    assert pkt.hex_dump() == "AA BB CC"
