from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import time

import numpy as np

from models.spectrum import SpectrumFrame
from models.waterfall import WaterfallMatrix


@dataclass(slots=True)
class WaterfallConfig:
    mode: str = "throttle"
    throttle_bin_size: float = 2.0
    time_rows: int = 300
    db_min: float = -90.0
    db_max: float = -20.0
    aggregation: str = "ema"
    ema_alpha: float = 0.2
    min_count_per_bin: int = 3
    display_freq_min: float = 2.0


class WaterfallBuilder:
    """Builds rolling time and throttle-binned waterfall matrices."""

    def __init__(self, config: WaterfallConfig) -> None:
        self.config = config
        self._freq_axis: np.ndarray | None = None
        self._time_rows: deque[np.ndarray] = deque(maxlen=config.time_rows)
        self._time_axis: deque[float] = deque(maxlen=config.time_rows)
        self._time_throttle: deque[float] = deque(maxlen=config.time_rows)
        self._throttle_matrix: np.ndarray | None = None
        self._count_per_bin: np.ndarray | None = None
        self._last_update_per_bin: np.ndarray | None = None

    def reset(self) -> None:
        self._freq_axis = None
        self._time_rows.clear()
        self._time_axis.clear()
        self._time_throttle.clear()
        self._throttle_matrix = None
        self._count_per_bin = None
        self._last_update_per_bin = None

    def update_config(self, config: WaterfallConfig) -> None:
        old_freq = self._freq_axis
        self.config = config
        self._time_rows = deque(self._time_rows, maxlen=config.time_rows)
        self._time_axis = deque(self._time_axis, maxlen=config.time_rows)
        self._time_throttle = deque(self._time_throttle, maxlen=config.time_rows)
        if old_freq is not None:
            self._ensure_throttle(old_freq)

    def add_frame(self, frame: SpectrumFrame) -> WaterfallMatrix:
        freqs, db = self._prepare_frame(frame)
        self._ensure_frequency(freqs)
        if self.config.mode == "time":
            self._time_rows.append(db)
            self._time_axis.append(frame.center_timestamp)
            self._time_throttle.append(np.nan if frame.throttle_percent is None else frame.throttle_percent)
            return self.get_time_matrix()
        self._ensure_throttle(freqs)
        if frame.throttle_percent is not None:
            bin_index = self._throttle_bin_index(frame.throttle_percent)
            self._aggregate_bin(bin_index, db)
        return self.get_throttle_matrix()

    def get_time_matrix(self) -> WaterfallMatrix:
        if self._freq_axis is None or not self._time_rows:
            return WaterfallMatrix("time", np.array([]), np.array([]), np.empty((0, 0)))
        matrix = np.vstack(list(self._time_rows))
        return WaterfallMatrix("time", self._freq_axis.copy(), np.asarray(self._time_axis), matrix, None)

    def get_throttle_matrix(self) -> WaterfallMatrix:
        if self._freq_axis is None:
            return WaterfallMatrix("throttle", np.array([]), np.array([]), np.empty((0, 0)), None)
        self._ensure_throttle(self._freq_axis)
        assert self._throttle_matrix is not None
        assert self._count_per_bin is not None
        return WaterfallMatrix(
            "throttle",
            self._freq_axis.copy(),
            self._throttle_axis(),
            self._throttle_matrix.copy(),
            self._count_per_bin[:, None].copy(),
        )

    def _prepare_frame(self, frame: SpectrumFrame) -> tuple[np.ndarray, np.ndarray]:
        freqs = np.asarray(frame.freqs, dtype=float)
        db = np.asarray(frame.db, dtype=float)
        mask = freqs >= self.config.display_freq_min
        return freqs[mask], db[mask]

    def _ensure_frequency(self, freqs: np.ndarray) -> None:
        if self._freq_axis is None:
            self._freq_axis = freqs.copy()
            return
        if self._freq_axis.shape != freqs.shape or not np.allclose(self._freq_axis, freqs):
            self.reset()
            self._freq_axis = freqs.copy()

    def _ensure_throttle(self, freqs: np.ndarray) -> None:
        bin_count = self._bin_count()
        if self._throttle_matrix is None or self._throttle_matrix.shape != (bin_count, freqs.size):
            self._throttle_matrix = np.full((bin_count, freqs.size), np.nan, dtype=float)
            self._count_per_bin = np.zeros(bin_count, dtype=int)
            self._last_update_per_bin = np.zeros(bin_count, dtype=float)

    def _bin_count(self) -> int:
        return int(np.floor(100.0 / self.config.throttle_bin_size)) + 1

    def _throttle_axis(self) -> np.ndarray:
        return np.arange(self._bin_count(), dtype=float) * self.config.throttle_bin_size

    def _throttle_bin_index(self, throttle_percent: float) -> int:
        idx = int(round(float(throttle_percent) / self.config.throttle_bin_size))
        return max(0, min(self._bin_count() - 1, idx))

    def _aggregate_bin(self, bin_index: int, db: np.ndarray) -> None:
        assert self._throttle_matrix is not None
        assert self._count_per_bin is not None
        assert self._last_update_per_bin is not None
        current = self._throttle_matrix[bin_index]
        count = self._count_per_bin[bin_index]
        if count == 0 or np.all(np.isnan(current)):
            self._throttle_matrix[bin_index] = db
        elif self.config.aggregation == "average":
            self._throttle_matrix[bin_index] = (current * count + db) / (count + 1)
        elif self.config.aggregation == "max_hold":
            self._throttle_matrix[bin_index] = np.maximum(current, db)
        elif self.config.aggregation == "ema":
            alpha = max(0.0, min(1.0, self.config.ema_alpha))
            self._throttle_matrix[bin_index] = alpha * db + (1.0 - alpha) * current
        else:
            raise ValueError(f"unsupported waterfall aggregation: {self.config.aggregation}")
        self._count_per_bin[bin_index] = count + 1
        self._last_update_per_bin[bin_index] = time.time()
