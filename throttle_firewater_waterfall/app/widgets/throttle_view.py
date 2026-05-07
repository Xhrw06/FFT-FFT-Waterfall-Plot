from __future__ import annotations

from collections import deque
import os

import numpy as np

os.environ.setdefault("PYQTGRAPH_QT_LIB", "PySide6")

import pyqtgraph as pg
from PySide6.QtWidgets import QVBoxLayout, QWidget

from models.samples import ThrottleSample


class ThrottleView(QWidget):
    def __init__(self, max_points: int = 1000, parent=None) -> None:
        super().__init__(parent)
        self.max_points = max_points
        self._timestamps: deque[float] = deque(maxlen=max_points)
        self._values: deque[float] = deque(maxlen=max_points)
        self.plot = pg.PlotWidget()
        self.plot.setLabel("bottom", "时间", units="s")
        self.plot.setLabel("left", "油门", units="%")
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.curve = self.plot.plot(pen=pg.mkPen("#f7c948", width=1.5))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.plot)

    def append(self, sample: ThrottleSample) -> None:
        if not self._timestamps:
            base = sample.timestamp
        else:
            base = self._timestamps[0]
        self._timestamps.append(sample.timestamp)
        self._values.append(sample.throttle_percent)
        x = np.asarray(self._timestamps, dtype=float) - base
        y = np.asarray(self._values, dtype=float)
        self.curve.setData(x, y)

    def clear(self) -> None:
        self._timestamps.clear()
        self._values.clear()
        self.curve.clear()
