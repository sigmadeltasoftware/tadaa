"""Frequency scanner for the CC1101 radio."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List


@dataclass
class ScanResult:
    """Result of measuring RSSI at a single frequency."""

    frequency_hz: int
    rssi_dbm: float
    noise_floor_dbm: float

    @property
    def signal_above_noise(self) -> float:
        """Signal-to-noise ratio in dB (SNR = RSSI - noise floor)."""
        return self.rssi_dbm - self.noise_floor_dbm


class FrequencyScanner:
    """Sweep a range of frequencies and measure RSSI at each step."""

    #: Default dwell time at each frequency before sampling RSSI (seconds).
    DEFAULT_DWELL_S: float = 0.005
    #: Default number of RSSI samples averaged per frequency step.
    DEFAULT_SAMPLES: int = 3
    #: Assumed noise floor when no external reference is available (dBm).
    DEFAULT_NOISE_FLOOR_DBM: float = -110.0

    def __init__(self, driver) -> None:
        """
        Parameters
        ----------
        driver:
            A :class:`~tadaa.cc1101.driver.CC1101Driver` instance (or compatible
            mock).
        """
        self._driver = driver

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def frequency_steps(
        start_hz: int,
        end_hz: int,
        step_hz: int,
    ) -> List[int]:
        """Return a list of frequencies from *start_hz* to *end_hz* inclusive.

        Parameters
        ----------
        start_hz:
            First frequency in Hz.
        end_hz:
            Last frequency in Hz (included if reachable by exact multiples of
            *step_hz*).
        step_hz:
            Step size in Hz.

        Returns
        -------
        list[int]
            Ascending list of integer frequencies.
        """
        freqs: List[int] = []
        freq = start_hz
        while freq <= end_hz:
            freqs.append(freq)
            freq += step_hz
        return freqs

    @staticmethod
    def find_peak(results: List[ScanResult]) -> ScanResult:
        """Return the :class:`ScanResult` with the highest RSSI.

        Parameters
        ----------
        results:
            Non-empty list of scan results.

        Returns
        -------
        ScanResult
            Entry whose *rssi_dbm* is highest (least negative).

        Raises
        ------
        ValueError
            If *results* is empty.
        """
        if not results:
            raise ValueError("Cannot find peak of an empty result list")
        return max(results, key=lambda r: r.rssi_dbm)

    # ------------------------------------------------------------------
    # Hardware-facing methods
    # ------------------------------------------------------------------

    def measure_rssi(
        self,
        frequency_hz: int,
        dwell_s: float = DEFAULT_DWELL_S,
        samples: int = DEFAULT_SAMPLES,
        noise_floor_dbm: float = DEFAULT_NOISE_FLOOR_DBM,
    ) -> ScanResult:
        """Tune to *frequency_hz*, enter RX mode, and return average RSSI.

        Parameters
        ----------
        frequency_hz:
            Carrier frequency to measure.
        dwell_s:
            Time to wait after entering RX before sampling (seconds).
        samples:
            Number of RSSI readings to average.
        noise_floor_dbm:
            Reference noise floor used to compute
            :attr:`ScanResult.signal_above_noise`.

        Returns
        -------
        ScanResult
            Measurement result at *frequency_hz*.
        """
        self._driver.set_idle()
        self._driver.set_frequency_hz(frequency_hz)
        self._driver.set_rx_mode()
        time.sleep(dwell_s)

        readings: list[float] = []
        for _ in range(samples):
            readings.append(self._driver.get_rssi())

        avg_rssi = sum(readings) / len(readings)
        self._driver.set_idle()

        return ScanResult(
            frequency_hz=frequency_hz,
            rssi_dbm=avg_rssi,
            noise_floor_dbm=noise_floor_dbm,
        )

    def scan(
        self,
        start_hz: int,
        end_hz: int,
        step_hz: int,
        dwell_s: float = DEFAULT_DWELL_S,
        samples: int = DEFAULT_SAMPLES,
        noise_floor_dbm: float = DEFAULT_NOISE_FLOOR_DBM,
    ) -> List[ScanResult]:
        """Perform a full frequency sweep and return all results.

        Parameters
        ----------
        start_hz:
            Start of scan range (Hz).
        end_hz:
            End of scan range (Hz, inclusive).
        step_hz:
            Step between measurement points (Hz).
        dwell_s:
            Per-frequency dwell time before RSSI sampling.
        samples:
            Number of RSSI readings averaged at each frequency.
        noise_floor_dbm:
            Reference noise floor for SNR calculation.

        Returns
        -------
        list[ScanResult]
            One result per frequency step, in ascending frequency order.
        """
        results: List[ScanResult] = []
        for freq in self.frequency_steps(start_hz, end_hz, step_hz):
            result = self.measure_rssi(
                freq,
                dwell_s=dwell_s,
                samples=samples,
                noise_floor_dbm=noise_floor_dbm,
            )
            results.append(result)
        return results
