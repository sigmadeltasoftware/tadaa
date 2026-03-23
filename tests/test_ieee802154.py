import pytest
from tadaa.packets.ieee802154 import parse_mac_frame, FrameType, MACFrame


def test_parse_beacon_frame_type():
    raw = bytes([0x00, 0x00, 0x01])
    frame = parse_mac_frame(raw)
    assert frame.frame_type == FrameType.BEACON
    assert frame.sequence_number == 0x01


def test_parse_data_frame_with_short_addresses():
    fc = 0x8841
    raw = bytes([
        fc & 0xFF, (fc >> 8) & 0xFF,
        0x05,
        0x34, 0x12,
        0x01, 0x00,
        0x02, 0x00,
        0xAA, 0xBB, 0xCC,
    ])
    frame = parse_mac_frame(raw)
    assert frame.frame_type == FrameType.DATA
    assert frame.sequence_number == 0x05
    assert frame.ack_request is False
    assert frame.security_enabled is False
    assert frame.dest_pan_id == 0x1234
    assert frame.dest_addr == b"\x01\x00"
    assert frame.src_addr == b"\x02\x00"
    assert frame.payload == b"\xAA\xBB\xCC"


def test_parse_ack_request_bit():
    fc = 0x8861
    raw = bytes([
        fc & 0xFF, (fc >> 8) & 0xFF,
        0x0A,
        0x34, 0x12,
        0x01, 0x00,
        0x02, 0x00,
        0xFF,
    ])
    frame = parse_mac_frame(raw)
    assert frame.ack_request is True


def test_parse_security_enabled_bit():
    fc = 0x8849
    raw = bytes([
        fc & 0xFF, (fc >> 8) & 0xFF,
        0x0B,
        0x34, 0x12,
        0x01, 0x00,
        0x02, 0x00,
        0xEE,
    ])
    frame = parse_mac_frame(raw)
    assert frame.security_enabled is True


def test_parse_too_short_raises():
    with pytest.raises(ValueError, match="too short"):
        parse_mac_frame(b"\x00\x00")


def test_frame_summary():
    fc = 0x8841
    raw = bytes([
        fc & 0xFF, (fc >> 8) & 0xFF,
        0x05,
        0x34, 0x12,
        0x01, 0x00,
        0x02, 0x00,
        0xAA, 0xBB,
    ])
    frame = parse_mac_frame(raw)
    summary = frame.summary()
    assert "DATA" in summary
    assert "0001" in summary or "0x0001" in summary
