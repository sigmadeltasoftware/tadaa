import pytest
from tadaa.sniffer.analyzer import TrafficAnalyzer
from tadaa.sniffer.capture import CapturedPacket


def _make_packet(raw: bytes, rssi: float = -70.0, ts: float = 0.0) -> CapturedPacket:
    return CapturedPacket(timestamp=ts, raw=raw, rssi_dbm=rssi, lqi=0x30)


def test_analyzer_counts_packets():
    fc = 0x8841
    frame1 = bytes([fc & 0xFF, (fc >> 8) & 0xFF, 0x01, 0x34, 0x12, 0x01, 0x00, 0x02, 0x00, 0xAA])
    frame2 = bytes([fc & 0xFF, (fc >> 8) & 0xFF, 0x02, 0x34, 0x12, 0x01, 0x00, 0x02, 0x00, 0xBB])
    analyzer = TrafficAnalyzer([_make_packet(frame1, ts=0.0), _make_packet(frame2, ts=1.0)])
    report = analyzer.analyze()
    assert report.total_packets == 2


def test_analyzer_detects_ack_usage():
    fc = 0x8861
    frame = bytes([fc & 0xFF, (fc >> 8) & 0xFF, 0x01, 0x34, 0x12, 0x01, 0x00, 0x02, 0x00, 0xAA])
    analyzer = TrafficAnalyzer([_make_packet(frame)])
    report = analyzer.analyze()
    assert report.uses_mac_acks is True


def test_analyzer_detects_no_ack():
    fc = 0x8841
    frame = bytes([fc & 0xFF, (fc >> 8) & 0xFF, 0x01, 0x34, 0x12, 0x01, 0x00, 0x02, 0x00, 0xAA])
    analyzer = TrafficAnalyzer([_make_packet(frame)])
    report = analyzer.analyze()
    assert report.uses_mac_acks is False


def test_analyzer_tracks_unique_addresses():
    fc = 0x8841
    frame1 = bytes([fc & 0xFF, (fc >> 8) & 0xFF, 0x01, 0x34, 0x12, 0x01, 0x00, 0x02, 0x00, 0xAA])
    frame2 = bytes([fc & 0xFF, (fc >> 8) & 0xFF, 0x02, 0x34, 0x12, 0x03, 0x00, 0x04, 0x00, 0xBB])
    analyzer = TrafficAnalyzer([_make_packet(frame1), _make_packet(frame2)])
    report = analyzer.analyze()
    assert len(report.unique_addresses) == 4


def test_analyzer_measures_inter_packet_gap():
    fc = 0x8841
    frame = bytes([fc & 0xFF, (fc >> 8) & 0xFF, 0x01, 0x34, 0x12, 0x01, 0x00, 0x02, 0x00, 0xAA])
    packets = [
        _make_packet(frame, ts=0.0),
        _make_packet(frame, ts=0.050),
        _make_packet(frame, ts=0.200),
    ]
    analyzer = TrafficAnalyzer(packets)
    report = analyzer.analyze()
    assert abs(report.min_inter_packet_ms - 50.0) < 1.0
    assert abs(report.avg_inter_packet_ms - 100.0) < 1.0


def test_analyzer_empty_buffer():
    analyzer = TrafficAnalyzer([])
    report = analyzer.analyze()
    assert report.total_packets == 0
