import pytest
from tadaa.packets.sixlowpan import parse_dispatch, DispatchType, SixLowPANHeader


def test_iphc_dispatch():
    data = bytes([0x7A, 0x33, 0xAA, 0xBB])
    header = parse_dispatch(data)
    assert header.dispatch_type == DispatchType.IPHC


def test_mesh_dispatch():
    data = bytes([0x80, 0x01, 0x02, 0x03])
    header = parse_dispatch(data)
    assert header.dispatch_type == DispatchType.MESH


def test_fragment_first_dispatch():
    data = bytes([0xC0, 0x10, 0x00, 0x05, 0xAA])
    header = parse_dispatch(data)
    assert header.dispatch_type == DispatchType.FRAG_FIRST


def test_fragment_subsequent_dispatch():
    data = bytes([0xE0, 0x10, 0x00, 0x05, 0x08, 0xBB])
    header = parse_dispatch(data)
    assert header.dispatch_type == DispatchType.FRAG_SUBSEQUENT


def test_uncompressed_ipv6_dispatch():
    data = bytes([0x41]) + b"\x00" * 40
    header = parse_dispatch(data)
    assert header.dispatch_type == DispatchType.IPV6


def test_unknown_dispatch():
    data = bytes([0x00, 0x00, 0x00])
    header = parse_dispatch(data)
    assert header.dispatch_type == DispatchType.UNKNOWN


def test_empty_data_raises():
    with pytest.raises(ValueError, match="empty"):
        parse_dispatch(b"")
