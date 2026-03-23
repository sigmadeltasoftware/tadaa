import time
import pytest
from tadaa.relay.daemon import RelayDaemon, RelayStats
from tadaa.relay.dedup import DeduplicationBuffer
from tadaa.cc1101.driver import CC1101Driver


def test_relay_stats_initial():
    stats = RelayStats()
    assert stats.packets_relayed == 0
    assert stats.packets_dropped == 0


def test_relay_stats_to_dict():
    stats = RelayStats()
    stats.packets_relayed = 10
    stats.packets_dropped = 2
    stats.last_rssi = -65.0
    d = stats.to_dict()
    assert d["packets_relayed"] == 10
    assert d["packets_dropped"] == 2
    assert "uptime" in d


def test_relay_processes_new_packet(fake_spi):
    driver = CC1101Driver(spi=fake_spi)
    daemon = RelayDaemon(driver)
    packet_data = b"\x41\x88\x05\x34\x12\x01\x00\x02\x00\xAA\xBB"
    result = daemon.process_packet(packet_data, rssi_dbm=-70.0)
    assert result is True
    assert daemon.stats.packets_relayed == 1


def test_relay_drops_duplicate(fake_spi):
    driver = CC1101Driver(spi=fake_spi)
    daemon = RelayDaemon(driver)
    packet = b"\x41\x88\x05\x34\x12\x01\x00\x02\x00\xAA\xBB"
    daemon.process_packet(packet, rssi_dbm=-70.0)
    result = daemon.process_packet(packet, rssi_dbm=-70.0)
    assert result is False
    assert daemon.stats.packets_dropped == 1
    assert daemon.stats.packets_relayed == 1


def test_relay_tracks_known_devices(fake_spi):
    driver = CC1101Driver(spi=fake_spi)
    daemon = RelayDaemon(driver)
    fc = 0x8841
    packet = bytes([fc & 0xFF, (fc >> 8) & 0xFF, 0x01, 0x34, 0x12, 0x01, 0x00, 0x02, 0x00, 0xAA])
    daemon.process_packet(packet, rssi_dbm=-70.0)
    assert len(daemon.stats.known_devices) > 0
