import pytest


class FakeSpiDev:
    """Mock spidev.SpiDev for testing without hardware."""

    def __init__(self):
        self.mode = 0
        self.max_speed_hz = 0
        self.registers: dict[int, int] = {}
        self._rx_fifo: bytes = b""
        self._tx_log: list[bytes] = []

    def open(self, bus: int, device: int) -> None:
        pass

    def close(self) -> None:
        pass

    def xfer2(self, data: list[int]) -> list[int]:
        header = data[0]
        status_byte = 0x0F

        if len(data) == 1:
            return [status_byte]

        addr = header & 0x3F
        is_read = bool(header & 0x80)
        is_burst = bool(header & 0x40)

        if addr == 0x3F and is_read:
            n = len(data) - 1
            fifo_data = self._rx_fifo[:n]
            self._rx_fifo = self._rx_fifo[n:]
            result = [status_byte] + list(fifo_data) + [0] * (n - len(fifo_data))
            return result

        if addr == 0x3F and not is_read:
            self._tx_log.append(bytes(data[1:]))
            return [status_byte] + [0] * (len(data) - 1)

        if is_read and is_burst:
            values = []
            for i in range(len(data) - 1):
                values.append(self.registers.get(addr + i, 0))
            return [status_byte] + values

        if is_read:
            val = self.registers.get(addr, 0)
            return [status_byte, val]

        self.registers[addr] = data[1]
        return [status_byte, 0]

    def load_rx_fifo(self, data: bytes) -> None:
        self._rx_fifo = data


@pytest.fixture
def fake_spi():
    return FakeSpiDev()
