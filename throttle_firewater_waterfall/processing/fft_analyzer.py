from __future__ import annotations

from dataclasses import dataclass
import time

import numpy as np

from models.spectrum import SpectrumFrame


@dataclass(slots=True)
class FFTConfig:
    sample_rate: float = 1000.0
    window_size: int = 1024
    overlap: float = 0.5
    window: str = "hann"
    remove_dc: bool = True
    detrend: bool = False
    freq_min: float = 0.0
    freq_max: float | None = 500.0
    ignore_below_hz: float = 2.0
    db_floor: float = -120.0


class FFTAnalyzer:
    """Windowed rFFT analyzer with mandatory pre-window DC protection option."""

    def __init__(self, config: FFTConfig) -> None:
        self.config = config

    @property
    def hop_size(self) -> int:
        hop = int(round(self.config.window_size * (1.0 - self.config.overlap)))
        return max(1, hop)

    def analyze(
        self,
        values: np.ndarray,
        timestamps: np.ndarray | None = None,
        *,
        throttle_percent: float | None = None,
        channel_name: str = "",
    ) -> SpectrumFrame:
        values = np.asarray(values, dtype=float)
        if values.size != self.config.window_size:
            raise ValueError(f"FFT window requires {self.config.window_size} samples, got {values.size}")
        if not np.all(np.isfinite(values)):
            finite = np.isfinite(values)
            if not finite.any():
                values = np.zeros_like(values)
            else:
                values = np.interp(np.arange(values.size), np.flatnonzero(finite), values[finite])

        x = values.astype(float, copy=True)

        if self.config.remove_dc:
            x = x - float(np.mean(x))
        if self.config.detrend:
            x = self._detrend_linear(x)

        window = self._window(self.config.window, self.config.window_size)
        xw = x * window
        spectrum = np.fft.rfft(xw)
        coherent_gain = np.sum(window) / self.config.window_size
        if coherent_gain <= 0:
            coherent_gain = 1.0
        magnitude = np.abs(spectrum) / (self.config.window_size * coherent_gain / 2.0)
        if magnitude.size:
            magnitude[0] *= 0.5
            if self.config.window_size % 2 == 0:
                magnitude[-1] *= 0.5
        freqs = np.fft.rfftfreq(self.config.window_size, d=1.0 / self.config.sample_rate)

        db = 20.0 * np.log10(np.maximum(magnitude, np.finfo(float).eps))
        db = np.maximum(db, self.config.db_floor)

        mask = freqs >= self.config.freq_min
        if self.config.freq_max is not None:
            mask &= freqs <= self.config.freq_max
        if self.config.ignore_below_hz > 0:
            low_mask = freqs < self.config.ignore_below_hz
            db = db.copy()
            db[low_mask] = self.config.db_floor

        now = time.time()
        if timestamps is not None and len(timestamps):
            center_timestamp = float(timestamps[len(timestamps) // 2])
            timestamp = float(timestamps[-1])
        else:
            center_timestamp = now
            timestamp = now

        return SpectrumFrame(
            timestamp=timestamp,
            center_timestamp=center_timestamp,
            throttle_percent=throttle_percent,
            channel_name=channel_name,
            freqs=freqs[mask],
            magnitude=magnitude[mask],
            db=db[mask],
        )

    @staticmethod
    def _window(name: str, size: int) -> np.ndarray:
        name = name.lower()
        if name in {"rect", "rectangular", "boxcar"}:
            return np.ones(size, dtype=float)
        if name == "hann":
            return np.hanning(size + 1)[:-1]
        if name == "hamming":
            return np.hamming(size + 1)[:-1]
        if name == "blackman":
            return np.blackman(size + 1)[:-1]
        raise ValueError(f"unsupported FFT window: {name}")

    @staticmethod
    def _detrend_linear(values: np.ndarray) -> np.ndarray:
        if values.size <= 1:
            return values
        x = np.arange(values.size, dtype=float)
        slope, intercept = np.polyfit(x, values, 1)
        return values - (slope * x + intercept)
