from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from serial_io.serial_scanner import list_serial_ports
from serial_io.serial_worker import SerialConfig


class SerialPanel(QWidget):
    refresh_requested = Signal()
    open_requested = Signal(object)
    close_requested = Signal()
    simulator_toggled = Signal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.port_combo = QComboBox()
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(
            ["115200", "230400", "460800", "921600", "1000000", "2000000", "3000000", "6000000"]
        )
        self.refresh_button = QPushButton("刷新")
        self.open_button = QPushButton("打开")
        self.close_button = QPushButton("关闭")
        self.simulator_check = QCheckBox("模拟数据模式")

        row = QHBoxLayout()
        row.addWidget(self.refresh_button)
        row.addWidget(self.open_button)
        row.addWidget(self.close_button)

        form = QFormLayout()
        form.addRow("串口号", self.port_combo)
        form.addRow("波特率", self.baud_combo)
        form.addRow("", self.simulator_check)

        group = QGroupBox("串口")
        inner = QVBoxLayout(group)
        inner.addLayout(form)
        inner.addLayout(row)

        layout = QVBoxLayout(self)
        layout.addWidget(group)
        layout.setContentsMargins(0, 0, 0, 0)

        self.refresh_button.clicked.connect(self.refresh_ports)
        self.open_button.clicked.connect(self._emit_open)
        self.close_button.clicked.connect(self.close_requested)
        self.simulator_check.toggled.connect(self.simulator_toggled)
        self.refresh_ports()

    def refresh_ports(self) -> None:
        current = self.port_combo.currentText()
        self.port_combo.clear()
        ports = list_serial_ports()
        self.port_combo.addItems(ports)
        if current:
            idx = self.port_combo.findText(current)
            if idx >= 0:
                self.port_combo.setCurrentIndex(idx)
        self.refresh_requested.emit()

    def serial_config(self) -> SerialConfig:
        return SerialConfig(
            port=self.port_combo.currentText(),
            baudrate=int(self.baud_combo.currentText() or "115200"),
        )

    def _emit_open(self) -> None:
        self.open_requested.emit(self.serial_config())
