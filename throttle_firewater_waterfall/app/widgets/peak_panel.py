from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QDoubleSpinBox, QFormLayout, QGroupBox, QSpinBox, QVBoxLayout, QWidget

from processing.peak_detector import PeakConfig


class PeakPanel(QWidget):
    config_changed = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.enable_check = QCheckBox("启用峰值检测")
        self.enable_check.setChecked(True)
        self.ignore_spin = QDoubleSpinBox()
        self.ignore_spin.setRange(0, 1000)
        self.ignore_spin.setValue(5)
        self.prom_spin = QDoubleSpinBox()
        self.prom_spin.setRange(0, 100)
        self.prom_spin.setValue(6)
        self.top_spin = QSpinBox()
        self.top_spin.setRange(1, 50)
        self.top_spin.setValue(5)

        form = QFormLayout()
        form.addRow("", self.enable_check)
        form.addRow("忽略低于 Hz", self.ignore_spin)
        form.addRow("prominence dB", self.prom_spin)
        form.addRow("Top N", self.top_spin)
        group = QGroupBox("峰值检测")
        group.setLayout(form)
        layout = QVBoxLayout(self)
        layout.addWidget(group)
        layout.setContentsMargins(0, 0, 0, 0)
        for widget in [self.enable_check, self.ignore_spin, self.prom_spin, self.top_spin]:
            signal = getattr(widget, "toggled", None) or getattr(widget, "valueChanged")
            signal.connect(self._emit)

    def config(self) -> PeakConfig:
        return PeakConfig(
            enabled=self.enable_check.isChecked(),
            ignore_below_hz=self.ignore_spin.value(),
            min_prominence_db=self.prom_spin.value(),
            top_n=self.top_spin.value(),
        )

    def _emit(self, *args) -> None:
        self.config_changed.emit(self.config())
