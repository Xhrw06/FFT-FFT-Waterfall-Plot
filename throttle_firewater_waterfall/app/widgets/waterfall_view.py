from __future__ import annotations

import os

import numpy as np

os.environ.setdefault("PYQTGRAPH_QT_LIB", "PySide6")

import pyqtgraph as pg
from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QVBoxLayout, QWidget

from models.waterfall import WaterfallMatrix


class WaterfallView(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.plot = pg.PlotWidget()
        self.plot.setLabel("bottom", "频率", units="Hz")
        self.plot.setLabel("left", "油门 / 时间")
        self.image = pg.ImageItem()
        self.plot.addItem(self.image)
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.db_min = -90.0
        self.db_max = -20.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.plot)

    def update_matrix(self, matrix: WaterfallMatrix) -> None:
        if matrix.db_matrix.size == 0 or matrix.freq_axis.size == 0 or matrix.y_axis.size == 0:
            self.image.clear()
            return
        data = np.asarray(matrix.db_matrix, dtype=float)
        data = np.nan_to_num(data, nan=self.db_min)
        self.image.setImage(
            data.T,
            autoLevels=False,
            levels=(self.db_min, self.db_max),
        )
        x_min = float(matrix.freq_axis[0])
        x_max = float(matrix.freq_axis[-1]) if matrix.freq_axis.size > 1 else x_min + 1.0
        y_min = float(matrix.y_axis[0])
        y_max = float(matrix.y_axis[-1]) if matrix.y_axis.size > 1 else y_min + 1.0
        self.image.setRect(QRectF(x_min, y_min, max(1e-9, x_max - x_min), max(1e-9, y_max - y_min)))
        self.plot.setLabel("left", "油门 %" if matrix.mode == "throttle" else "时间")

    def set_db_range(self, db_min: float, db_max: float) -> None:
        self.db_min = float(db_min)
        self.db_max = float(db_max)

    def clear(self) -> None:
        self.image.clear()
