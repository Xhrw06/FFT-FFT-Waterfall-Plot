from __future__ import annotations

from PySide6.QtWidgets import QLabel, QStatusBar


class AppStatusBar(QStatusBar):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.runtime_label = QLabel("就绪")
        self.file_label = QLabel("未保存")
        self.stats_label = QLabel("0 lines")
        self.warning_label = QLabel("")
        self.addWidget(self.runtime_label, 1)
        self.addPermanentWidget(self.file_label)
        self.addPermanentWidget(self.stats_label)
        self.addPermanentWidget(self.warning_label)

    def set_runtime(self, text: str) -> None:
        self.runtime_label.setText(text)

    def set_file(self, text: str) -> None:
        self.file_label.setText(text)

    def set_stats(self, text: str) -> None:
        self.stats_label.setText(text)

    def set_warning(self, text: str) -> None:
        self.warning_label.setText(text)
