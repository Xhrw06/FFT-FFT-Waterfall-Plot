from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class WaterfallMatrix:
    mode: str
    freq_axis: np.ndarray
    y_axis: np.ndarray
    db_matrix: np.ndarray
    count_matrix: np.ndarray | None = None
