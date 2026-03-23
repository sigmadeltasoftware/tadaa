import time
import pytest
from tadaa.relay.dedup import DeduplicationBuffer


def test_new_packet_is_not_duplicate():
    buf = DeduplicationBuffer(ttl_seconds=5.0)
    assert buf.is_duplicate(b"\x01\x02\x03") is False


def test_same_packet_is_duplicate():
    buf = DeduplicationBuffer(ttl_seconds=5.0)
    buf.is_duplicate(b"\x01\x02\x03")
    assert buf.is_duplicate(b"\x01\x02\x03") is True


def test_different_packet_is_not_duplicate():
    buf = DeduplicationBuffer(ttl_seconds=5.0)
    buf.is_duplicate(b"\x01\x02\x03")
    assert buf.is_duplicate(b"\x04\x05\x06") is False


def test_expired_packet_is_not_duplicate():
    buf = DeduplicationBuffer(ttl_seconds=0.05)
    buf.is_duplicate(b"\x01\x02\x03")
    time.sleep(0.06)
    assert buf.is_duplicate(b"\x01\x02\x03") is False


def test_cleanup_removes_expired():
    buf = DeduplicationBuffer(ttl_seconds=0.05)
    buf.is_duplicate(b"\x01")
    buf.is_duplicate(b"\x02")
    time.sleep(0.06)
    buf.cleanup()
    assert len(buf) == 0


def test_stats_tracking():
    buf = DeduplicationBuffer(ttl_seconds=5.0)
    buf.is_duplicate(b"\x01")
    buf.is_duplicate(b"\x01")
    buf.is_duplicate(b"\x02")
    buf.is_duplicate(b"\x01")
    assert buf.stats_new == 2
    assert buf.stats_duplicate == 2
