from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QVBoxLayout, QWidget


class AcquisitionPanel(QWidget):
    config_changed = Signal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["manual", "estimated"])
        self.sample_rate_spin = QDoubleSpinBox()
        self.sample_rate_spin.setRange(1, 200000)
        self.sample_rate_spin.setValue(1000)
        self.sample_rate_spin.setDecimals(1)

        form = QFormLayout()
        form.addRow("采样率模式", self.mode_combo)
        form.addRow("采样率 Hz", self.sample_rate_spin)
        group = QGroupBox("采集")
        group.setLayout(form)
        layout = QVBoxLayout(self)
        layout.addWidget(group)
        layout.setContentsMargins(0, 0, 0, 0)
        self.mode_combo.currentTextChanged.connect(self._emit)
        self.sample_rate_spin.valueChanged.connect(self._emit)

    def config(self) -> dict:
        return {"sample_rate_mode": self.mode_combo.currentText(), "sample_rate": self.sample_rate_spin.value()}

    def _emit(self) -> None:
        self.config_changed.emit(self.config())
