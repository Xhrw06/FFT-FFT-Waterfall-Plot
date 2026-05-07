from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QSpinBox, QVBoxLayout, QWidget

from processing.fft_analyzer import FFTConfig


class FFTPanel(QWidget):
    config_changed = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.sample_rate_spin = QDoubleSpinBox()
        self.sample_rate_spin.setRange(1, 200000)
        self.sample_rate_spin.setValue(1000)
        self.window_size_combo = QComboBox()
        self.window_size_combo.addItems(["256", "512", "1024", "2048", "4096"])
        self.window_size_combo.setCurrentText("1024")
        self.overlap_combo = QComboBox()
        self.overlap_combo.addItems(["0", "0.25", "0.5", "0.75"])
        self.overlap_combo.setCurrentText("0.5")
        self.window_combo = QComboBox()
        self.window_combo.addItems(["hann", "hamming", "blackman", "rectangular"])
        self.freq_min_spin = QDoubleSpinBox()
        self.freq_min_spin.setRange(0, 100000)
        self.freq_max_spin = QDoubleSpinBox()
        self.freq_max_spin.setRange(1, 100000)
        self.freq_max_spin.setValue(500)
        self.ignore_spin = QDoubleSpinBox()
        self.ignore_spin.setRange(0, 1000)
        self.ignore_spin.setValue(2)
        self.remove_dc_check = QCheckBox("remove DC")
        self.remove_dc_check.setChecked(True)
        self.detrend_check = QCheckBox("detrend")

        form = QFormLayout()
        form.addRow("采样率", self.sample_rate_spin)
        form.addRow("窗口长度", self.window_size_combo)
        form.addRow("overlap", self.overlap_combo)
        form.addRow("窗函数", self.window_combo)
        form.addRow("freq min", self.freq_min_spin)
        form.addRow("freq max", self.freq_max_spin)
        form.addRow("忽略低于 Hz", self.ignore_spin)
        form.addRow("", self.remove_dc_check)
        form.addRow("", self.detrend_check)
        group = QGroupBox("FFT 参数")
        group.setLayout(form)
        layout = QVBoxLayout(self)
        layout.addWidget(group)
        layout.setContentsMargins(0, 0, 0, 0)

        widgets = [
            self.sample_rate_spin,
            self.window_size_combo,
            self.overlap_combo,
            self.window_combo,
            self.freq_min_spin,
            self.freq_max_spin,
            self.ignore_spin,
            self.remove_dc_check,
            self.detrend_check,
        ]
        for widget in widgets:
            signal = getattr(widget, "toggled", None) or getattr(widget, "currentTextChanged", None) or getattr(widget, "valueChanged")
            signal.connect(self._emit)

    def config(self) -> FFTConfig:
        return FFTConfig(
            sample_rate=self.sample_rate_spin.value(),
            window_size=int(self.window_size_combo.currentText()),
            overlap=float(self.overlap_combo.currentText()),
            window=self.window_combo.currentText(),
            remove_dc=self.remove_dc_check.isChecked(),
            detrend=self.detrend_check.isChecked(),
            freq_min=self.freq_min_spin.value(),
            freq_max=self.freq_max_spin.value(),
            ignore_below_hz=self.ignore_spin.value(),
        )

    def _emit(self, *args) -> None:
        self.config_changed.emit(self.config())
