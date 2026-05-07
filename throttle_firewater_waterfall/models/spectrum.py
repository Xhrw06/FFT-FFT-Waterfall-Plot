from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class SpectrumFrame:
    timestamp: float
    center_timestamp: float
    throttle_percent: float | None
    channel_name: str
    freqs: np.ndarray
    magnitude: np.ndarray
    db: np.ndarray
