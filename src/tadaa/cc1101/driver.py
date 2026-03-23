"""CC1101 SPI driver."""

from __future__ import annotations

from tadaa.cc1101.registers import (
    ConfigReg,
    StatusReg,
    Strobe,
    FIFO_ADDR,
    READ_SINGLE,
    READ_BURST,
    WRITE_SINGLE,
    WRITE_BURST,
    XTAL_FREQ_HZ,
)


class CC1101Driver:
    """Low-level CC1101 driver wrapping spidev.

    Pass *spi* to inject a mock for tests; omit it to have the driver create
    a real ``spidev.SpiDev`` instance on *bus*/*device*.
    """

    def __init__(
        self,
        spi=None,
        bus: int = 0,
        device: int = 0,
        speed_hz: int = 500_000,
    ) -> None:
        if spi is not None:
            self._spi = spi
        else:
            import spidev  # type: ignore[import]
            self._spi = spidev.SpiDev()
            self._spi.open(bus, device)
            self._spi.max_speed_hz = speed_hz
            self._spi.mode = 0

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------
    def __enter__(self) -> "CC1101Driver":
        return self

    def __exit__(self, *_) -> None:
        self._spi.close()

    # ------------------------------------------------------------------
    # Low-level SPI primitives
    # ------------------------------------------------------------------
    def write_register(self, reg: ConfigReg, value: int) -> None:
        """Write a single configuration register."""
        self._spi.xfer2([WRITE_SINGLE | int(reg), value & 0xFF])

    def read_register(self, reg: ConfigReg) -> int:
        """Read a single configuration register."""
        result = self._spi.xfer2([READ_SINGLE | int(reg), 0x00])
        return result[1]

    def read_status_register(self, reg: StatusReg) -> int:
        """Read a status register.

        Status registers share addresses with strobes; using READ_BURST
        distinguishes a register read from a strobe command.
        """
        result = self._spi.xfer2([READ_BURST | int(reg), 0x00])
        return result[1]

    def strobe(self, command: Strobe) -> int:
        """Send a command strobe. Returns the chip status byte."""
        result = self._spi.xfer2([int(command)])
        return result[0]

    def read_rx_fifo(self, n: int) -> bytes:
        """Read *n* bytes from the RX FIFO in a single burst transfer."""
        data = [READ_BURST | FIFO_ADDR] + [0x00] * n
        result = self._spi.xfer2(data)
        return bytes(result[1:])

    def write_tx_fifo(self, payload: bytes) -> None:
        """Write *payload* to the TX FIFO in a single burst transfer."""
        data = [WRITE_BURST | FIFO_ADDR] + list(payload)
        self._spi.xfer2(data)

    # ------------------------------------------------------------------
    # Higher-level helpers
    # ------------------------------------------------------------------
    def set_frequency_hz(self, freq_hz: int) -> None:
        """Program FREQ2/FREQ1/FREQ0 for the requested carrier frequency."""
        freq_word = round(freq_hz * (1 << 16) / XTAL_FREQ_HZ)
        freq2 = (freq_word >> 16) & 0xFF
        freq1 = (freq_word >> 8) & 0xFF
        freq0 = freq_word & 0xFF
        self.write_register(ConfigReg.FREQ2, freq2)
        self.write_register(ConfigReg.FREQ1, freq1)
        self.write_register(ConfigReg.FREQ0, freq0)

    @staticmethod
    def rssi_to_dbm(rssi_dec: int) -> float:
        """Convert raw RSSI register value to dBm (datasheet section 17.3)."""
        if rssi_dec >= 128:
            return (rssi_dec - 256) / 2.0 - 74.0
        return rssi_dec / 2.0 - 74.0

    def get_rssi(self) -> float:
        """Return current RSSI in dBm."""
        raw = self.read_status_register(StatusReg.RSSI)
        return self.rssi_to_dbm(raw)

    def get_marcstate(self) -> int:
        """Return raw MARCSTATE value."""
        return self.read_status_register(StatusReg.MARCSTATE) & 0x1F

    def get_rx_bytes(self) -> int:
        """Return number of bytes available in the RX FIFO."""
        return self.read_status_register(StatusReg.RXBYTES) & 0x7F

    # ------------------------------------------------------------------
    # Convenience state transitions
    # ------------------------------------------------------------------
    def reset(self) -> None:
        """Issue SRES strobe to reset the chip."""
        self.strobe(Strobe.SRES)

    def set_rx_mode(self) -> None:
        """Transition chip to RX state."""
        self.strobe(Strobe.SRX)

    def set_idle(self) -> None:
        """Transition chip to IDLE state."""
        self.strobe(Strobe.SIDLE)

    def flush_rx(self) -> None:
        """Flush the RX FIFO (chip must be in IDLE first)."""
        self.strobe(Strobe.SFRX)

    def flush_tx(self) -> None:
        """Flush the TX FIFO (chip must be in IDLE first)."""
        self.strobe(Strobe.SFTX)
