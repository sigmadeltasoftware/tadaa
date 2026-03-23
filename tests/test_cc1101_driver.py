import pytest
from tadaa.cc1101.driver import CC1101Driver
from tadaa.cc1101.registers import ConfigReg, StatusReg, Strobe, XTAL_FREQ_HZ


def test_write_register(fake_spi):
    driver = CC1101Driver(spi=fake_spi)
    driver.write_register(ConfigReg.PKTLEN, 0x40)
    assert fake_spi.registers[ConfigReg.PKTLEN] == 0x40


def test_read_register(fake_spi):
    fake_spi.registers[ConfigReg.PKTLEN] = 0x20
    driver = CC1101Driver(spi=fake_spi)
    assert driver.read_register(ConfigReg.PKTLEN) == 0x20


def test_frequency_calculation(fake_spi):
    driver = CC1101Driver(spi=fake_spi)
    driver.set_frequency_hz(868_000_000)
    freq2 = fake_spi.registers[ConfigReg.FREQ2]
    freq1 = fake_spi.registers[ConfigReg.FREQ1]
    freq0 = fake_spi.registers[ConfigReg.FREQ0]
    freq_word = (freq2 << 16) | (freq1 << 8) | freq0
    calculated_hz = (freq_word * XTAL_FREQ_HZ) / (1 << 16)
    assert abs(calculated_hz - 868_000_000) < 1000


def test_rssi_conversion(fake_spi):
    driver = CC1101Driver(spi=fake_spi)
    assert driver.rssi_to_dbm(0x00) == -74.0
    assert driver.rssi_to_dbm(0x80) == -138.0
    assert driver.rssi_to_dbm(0xA0) == -122.0


def test_read_rx_fifo(fake_spi):
    fake_spi.load_rx_fifo(b"\x05\xAA\xBB\xCC\xDD\xEE")
    driver = CC1101Driver(spi=fake_spi)
    data = driver.read_rx_fifo(6)
    assert data == b"\x05\xAA\xBB\xCC\xDD\xEE"


def test_strobe_command(fake_spi):
    driver = CC1101Driver(spi=fake_spi)
    driver.strobe(Strobe.SRES)
    driver.strobe(Strobe.SRX)
    driver.strobe(Strobe.SIDLE)
