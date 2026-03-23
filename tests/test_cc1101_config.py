from tadaa.cc1101.config import RadioConfig, SCAN_CONFIGS


def test_radio_config_has_required_fields():
    cfg = RadioConfig(
        name="test",
        frequency_hz=868_000_000,
        data_rate_baud=38400,
        modulation=0x10,
        deviation_hz=20_000,
        sync_word=0xD391,
        bandwidth_khz=100,
    )
    assert cfg.frequency_hz == 868_000_000
    assert cfg.data_rate_baud == 38400


def test_scan_configs_cover_expected_frequencies():
    freqs = {c.frequency_hz for c in SCAN_CONFIGS}
    assert any(868_000_000 <= f <= 868_600_000 for f in freqs)


def test_scan_configs_cover_modulations():
    mods = {c.modulation for c in SCAN_CONFIGS}
    assert 0x10 in mods  # GFSK
    assert 0x00 in mods  # 2-FSK


def test_data_rate_register_calculation():
    cfg = RadioConfig(
        name="test",
        frequency_hz=868_000_000,
        data_rate_baud=38400,
        modulation=0x10,
        deviation_hz=20_000,
        sync_word=0xD391,
        bandwidth_khz=100,
    )
    mantissa, exponent = cfg.calc_data_rate_regs()
    xtal = 26_000_000
    rate = ((256 + mantissa) * (2 ** exponent) * xtal) / (1 << 28)
    assert abs(rate - 38400) < 500
