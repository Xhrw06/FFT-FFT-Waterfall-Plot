from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

from models.firewater import FireWaterLine


class ProtocolPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.prefix_label = QLabel("-")
        self.raw_label = QLabel("-")
        self.raw_label.setWordWrap(True)
        self.field_count_label = QLabel("0")
        self.known_prefix_label = QLabel("-")
        self.unconfigured_label = QLabel("-")

        form = QFormLayout()
        form.addRow("当前 prefix", self.prefix_label)
        form.addRow("最近一行", self.raw_label)
        form.addRow("字段数量", self.field_count_label)
        form.addRow("已知 prefix", self.known_prefix_label)
        form.addRow("未配置提示", self.unconfigured_label)

        group = QGroupBox("FireWater 状态")
        group.setLayout(form)
        layout = QVBoxLayout(self)
        layout.addWidget(group)
        layout.setContentsMargins(0, 0, 0, 0)

    def update_line(self, line: FireWaterLine, known_prefixes: list[str], configured: bool = True) -> None:
        self.prefix_label.setText(line.prefix or "无前缀数据")
        self.raw_label.setText(line.raw_line)
        self.field_count_label.setText(str(len(line.values)))
        self.known_prefix_label.setText(", ".join(prefix or "无前缀数据" for prefix in known_prefixes))
        self.unconfigured_label.setText("已配置" if configured else f"未配置：{line.prefix or '无前缀数据'}")
