import pytest
from tadaa.sniffer.scanner import FrequencyScanner, ScanResult


def test_scan_result_fields():
    result = ScanResult(frequency_hz=868_000_000, rssi_dbm=-80.0, noise_floor_dbm=-110.0)
    assert result.frequency_hz == 868_000_000
    assert result.signal_above_noise == 30.0


def test_scanner_generates_frequency_steps(fake_spi):
    from tadaa.cc1101.driver import CC1101Driver
    driver = CC1101Driver(spi=fake_spi)
    scanner = FrequencyScanner(driver)
    freqs = scanner.frequency_steps(
        start_hz=868_000_000,
        end_hz=868_600_000,
        step_hz=50_000,
    )
    assert freqs[0] == 868_000_000
    assert freqs[-1] == 868_600_000
    assert len(freqs) == 13


def test_scanner_identifies_peak():
    results = [
        ScanResult(868_000_000, -100.0, -110.0),
        ScanResult(868_050_000, -95.0, -110.0),
        ScanResult(868_100_000, -65.0, -110.0),
        ScanResult(868_150_000, -90.0, -110.0),
        ScanResult(868_200_000, -105.0, -110.0),
    ]
    peak = FrequencyScanner.find_peak(results)
    assert peak.frequency_hz == 868_100_000
