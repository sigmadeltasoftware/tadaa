"""Radio configuration presets for CC1101."""

from __future__ import annotations

import math
from dataclasses import dataclass

from tadaa.cc1101.registers import (
    MOD_2FSK,
    MOD_GFSK,
    SYNC_WORD_DEFAULT,
    SYNC_WORD_TADO,
    XTAL_FREQ_HZ,
)


@dataclass(frozen=True)
class RadioConfig:
    """Immutable description of a CC1101 radio configuration.

    All frequency/rate values are in SI units (Hz, baud).
    """

    name: str
    frequency_hz: int
    data_rate_baud: int
    modulation: int          # MDMCFG2[5:4] value, e.g. MOD_GFSK = 0x10
    deviation_hz: int
    sync_word: int
    bandwidth_khz: float

    # ------------------------------------------------------------------
    # Register calculation helpers
    # ------------------------------------------------------------------

    def calc_data_rate_regs(self) -> tuple[int, int]:
        """Return (DRATE_M, DRATE_E) for MDMCFG3/MDMCFG4.

        Formula (datasheet section 13):
            data_rate = (256 + DRATE_M) * 2^DRATE_E * f_XOSC / 2^28
        """
        best_mantissa = 0
        best_exponent = 0
        best_error = float("inf")

        for exp in range(16):
            # mantissa = data_rate * 2^28 / (f_XOSC * 2^exp) - 256
            mantissa_f = self.data_rate_baud * (1 << 28) / (XTAL_FREQ_HZ * (1 << exp)) - 256
            for m in (math.floor(mantissa_f), math.ceil(mantissa_f)):
                if not (0 <= m <= 255):
                    continue
                actual = (256 + m) * (1 << exp) * XTAL_FREQ_HZ / (1 << 28)
                error = abs(actual - self.data_rate_baud)
                if error < best_error:
                    best_error = error
                    best_mantissa = m
                    best_exponent = exp

        return best_mantissa, best_exponent

    def calc_deviation_regs(self) -> tuple[int, int]:
        """Return (DEVIATION_M, DEVIATION_E) for DEVIATN register.

        Formula (datasheet section 16.1):
            f_dev = f_XOSC / 2^17 * (8 + DEVIATION_M) * 2^DEVIATION_E
        where DEVIATION_M is 0-7 and DEVIATION_E is 0-7.
        """
        best_mantissa = 0
        best_exponent = 0
        best_error = float("inf")

        for exp in range(8):
            # mantissa_f = f_dev * 2^17 / (f_XOSC * 2^exp) - 8
            mantissa_f = self.deviation_hz * (1 << 17) / (XTAL_FREQ_HZ * (1 << exp)) - 8
            for m in (math.floor(mantissa_f), math.ceil(mantissa_f)):
                if not (0 <= m <= 7):
                    continue
                actual = XTAL_FREQ_HZ / (1 << 17) * (8 + m) * (1 << exp)
                error = abs(actual - self.deviation_hz)
                if error < best_error:
                    best_error = error
                    best_mantissa = m
                    best_exponent = exp

        return best_mantissa, best_exponent


# ---------------------------------------------------------------------------
# Scan configuration presets
#
# Tado V3+ is known to use 868.3 MHz with GFSK modulation.
# We add a range of rates and modulations to maximise detection probability.
# ---------------------------------------------------------------------------
SCAN_CONFIGS: list[RadioConfig] = [
    # Primary Tado channel — GFSK 38.4 kBaud at 868.3 MHz
    # Tado uses CC1101 default sync word byte-swapped: 0x91D3
    RadioConfig(
        name="tado_primary_gfsk_38k4",
        frequency_hz=868_300_000,
        data_rate_baud=38_400,
        modulation=MOD_GFSK,
        deviation_hz=20_000,
        sync_word=SYNC_WORD_TADO,
        bandwidth_khz=100.0,
    ),
    # GFSK at a lower rate — catches slower Tado variants
    RadioConfig(
        name="tado_gfsk_9k6",
        frequency_hz=868_300_000,
        data_rate_baud=9_600,
        modulation=MOD_GFSK,
        deviation_hz=5_000,
        sync_word=SYNC_WORD_DEFAULT,
        bandwidth_khz=50.0,
    ),
    # 2-FSK fallback at 868 MHz
    RadioConfig(
        name="868_2fsk_38k4",
        frequency_hz=868_000_000,
        data_rate_baud=38_400,
        modulation=MOD_2FSK,
        deviation_hz=20_000,
        sync_word=SYNC_WORD_DEFAULT,
        bandwidth_khz=100.0,
    ),
    # 2-FSK at 868.6 MHz (upper band edge used by some meters)
    RadioConfig(
        name="868_6_2fsk_38k4",
        frequency_hz=868_600_000,
        data_rate_baud=38_400,
        modulation=MOD_2FSK,
        deviation_hz=20_000,
        sync_word=SYNC_WORD_DEFAULT,
        bandwidth_khz=100.0,
    ),
    # GFSK high rate — 868.95 MHz wMBus T-mode / OMS
    RadioConfig(
        name="wmbus_t_gfsk_100k",
        frequency_hz=868_950_000,
        data_rate_baud=100_000,
        modulation=MOD_GFSK,
        deviation_hz=50_000,
        sync_word=0x543D,
        bandwidth_khz=200.0,
    ),
]
