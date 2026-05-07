from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout


class ExportDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("导出")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("导出 PNG、CSV、Markdown、HTML 报告的入口已预留在 storage/export_report.py。"))
