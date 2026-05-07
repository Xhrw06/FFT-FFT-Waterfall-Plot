from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from models.spectrum import SpectrumFrame


@dataclass(slots=True)
class PeakConfig:
    enabled: bool = True
    ignore_below_hz: float = 5.0
    top_n: int = 5
    min_prominence_db: float = 6.0
    min_height_db: float | None = None


@dataclass(slots=True)
class PeakRecord:
    timestamp: float
    throttle: float | None
    frequency: float
    db: float
    channel: str


class PeakDetector:
    def __init__(self, config: PeakConfig) -> None:
        self.config = config
        self.records: list[PeakRecord] = []

    def update_config(self, config: PeakConfig) -> None:
        self.config = config

    def detect(self, frame: SpectrumFrame) -> list[PeakRecord]:
        if not self.config.enabled or frame.freqs.size == 0:
            return []
        mask = frame.freqs >= self.config.ignore_below_hz
        freqs = frame.freqs[mask]
        db = frame.db[mask]
        if freqs.size == 0:
            return []
        indices = self._find_peaks(db)
        ranked = sorted(indices, key=lambda i: db[i], reverse=True)[: self.config.top_n]
        records = [
            PeakRecord(
                timestamp=frame.center_timestamp,
                throttle=frame.throttle_percent,
                frequency=float(freqs[index]),
                db=float(db[index]),
                channel=frame.channel_name,
            )
            for index in ranked
        ]
        self.records.extend(records)
        return records

    def _find_peaks(self, values: np.ndarray) -> list[int]:
        if values.size < 3:
            return []
        peaks: list[int] = []
        for index in range(1, values.size - 1):
            current = values[index]
            if self.config.min_height_db is not None and current < self.config.min_height_db:
                continue
            if current <= values[index - 1] or current < values[index + 1]:
                continue
            left_min = float(np.min(values[: index + 1]))
            right_min = float(np.min(values[index:]))
            prominence = current - max(left_min, right_min)
            if prominence >= self.config.min_prominence_db:
                peaks.append(index)
        return peaks
