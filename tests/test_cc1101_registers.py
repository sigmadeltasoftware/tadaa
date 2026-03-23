from tadaa.cc1101.registers import (
    ConfigReg, StatusReg, Strobe,
    SYNC_WORD_DEFAULT, PKTCTRL0_FIXED_LENGTH,
)


def test_config_register_addresses_are_in_range():
    """Config registers are 0x00-0x2E per datasheet."""
    for reg in ConfigReg:
        assert 0x00 <= reg.value <= 0x2E, f"{reg.name} = 0x{reg.value:02X} out of range"


def test_status_register_addresses_are_in_range():
    """Status registers are 0x30-0x3D per datasheet."""
    for reg in StatusReg:
        assert 0x30 <= reg.value <= 0x3D, f"{reg.name} = 0x{reg.value:02X} out of range"


def test_strobe_addresses_are_in_range():
    """Strobe commands are 0x30-0x3D per datasheet."""
    for strobe in Strobe:
        assert 0x30 <= strobe.value <= 0x3D, f"{strobe.name} = 0x{strobe.value:02X} out of range"


def test_key_registers_exist():
    """Verify critical registers for our use case are defined."""
    assert ConfigReg.FREQ2.value == 0x0D
    assert ConfigReg.FREQ1.value == 0x0E
    assert ConfigReg.FREQ0.value == 0x0F
    assert ConfigReg.MDMCFG4.value == 0x10
    assert ConfigReg.MDMCFG3.value == 0x11
    assert ConfigReg.MDMCFG2.value == 0x12
    assert StatusReg.RSSI.value == 0x34
    assert StatusReg.MARCSTATE.value == 0x35


def test_sync_word_default():
    assert SYNC_WORD_DEFAULT == 0xD391
