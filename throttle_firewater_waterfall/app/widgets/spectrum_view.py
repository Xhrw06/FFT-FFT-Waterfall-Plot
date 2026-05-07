from __future__ import annotations

import os

os.environ.setdefault("PYQTGRAPH_QT_LIB", "PySide6")

import pyqtgraph as pg
from PySide6.QtWidgets import QVBoxLayout, QWidget

from models.spectrum import SpectrumFrame


class SpectrumView(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.plot = pg.PlotWidget()
        self.plot.setLabel("bottom", "频率", units="Hz")
        self.plot.setLabel("left", "幅值", units="dB")
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.curve = self.plot.plot(pen=pg.mkPen("#6bd2ff", width=1.5))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.plot)

    def update_spectrum(self, frame: SpectrumFrame) -> None:
        self.curve.setData(frame.freqs, frame.db)

    def clear(self) -> None:
        self.curve.clear()
