from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from models.preprocess import PreprocessConfig


class PreprocessPanel(QWidget):
    config_changed = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.enable_check = QCheckBox("启用去直流")
        self.enable_check.setChecked(True)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["window_mean", "running_mean", "ema", "highpass", "detrend", "none"])
        self.ema_spin = QDoubleSpinBox()
        self.ema_spin.setRange(0, 1)
        self.ema_spin.setSingleStep(0.01)
        self.ema_spin.setValue(0.01)
        self.running_spin = QDoubleSpinBox()
        self.running_spin.setRange(0.01, 60)
        self.running_spin.setValue(2.0)
        self.highpass_spin = QDoubleSpinBox()
        self.highpass_spin.setRange(0.01, 1000)
        self.highpass_spin.setValue(1.0)
        self.order_spin = QSpinBox()
        self.order_spin.setRange(1, 8)
        self.order_spin.setValue(2)
        self.window_mean_check = QCheckBox("FFT 窗口再去均值")
        self.window_mean_check.setChecked(True)
        self.detrend_check = QCheckBox("FFT detrend")
        self.dc_label = QLabel("-")

        form = QFormLayout()
        form.addRow("", self.enable_check)
        form.addRow("去直流模式", self.mode_combo)
        form.addRow("EMA alpha", self.ema_spin)
        form.addRow("滑动窗口 s", self.running_spin)
        form.addRow("高通截止 Hz", self.highpass_spin)
        form.addRow("高通阶数", self.order_spin)
        form.addRow("", self.window_mean_check)
        form.addRow("", self.detrend_check)
        form.addRow("当前 DC", self.dc_label)
        group = QGroupBox("信号预处理 / 直流偏置处理")
        group.setLayout(form)
        layout = QVBoxLayout(self)
        layout.addWidget(group)
        layout.setContentsMargins(0, 0, 0, 0)

        for widget in [
            self.enable_check,
            self.mode_combo,
            self.ema_spin,
            self.running_spin,
            self.highpass_spin,
            self.order_spin,
            self.window_mean_check,
            self.detrend_check,
        ]:
            signal = getattr(widget, "toggled", None) or getattr(widget, "currentTextChanged", None) or getattr(widget, "valueChanged")
            signal.connect(self._emit)

    def config(self, sample_rate: float = 1000.0) -> PreprocessConfig:
        return PreprocessConfig(
            dc_enabled=self.enable_check.isChecked(),
            dc_mode=self.mode_combo.currentText(),
            ema_alpha=self.ema_spin.value(),
            running_mean_window_sec=self.running_spin.value(),
            highpass_cutoff_hz=self.highpass_spin.value(),
            highpass_order=self.order_spin.value(),
            sample_rate=sample_rate,
            fft_remove_window_mean=self.window_mean_check.isChecked(),
            detrend_enabled=self.detrend_check.isChecked(),
        )

    def set_dc_estimate(self, channel: str, value: float | None) -> None:
        self.dc_label.setText(f"{channel}: {value:.4g}" if value is not None else "-")

    def _emit(self, *args) -> None:
        self.config_changed.emit(self.config())
