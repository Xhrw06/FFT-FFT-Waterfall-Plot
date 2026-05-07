from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QFileDialog, QListWidget, QPushButton, QHBoxLayout, QVBoxLayout

from storage.profile_store import ProfileStore


class ProfileManagerDialog(QDialog):
    profile_loaded = Signal(object)

    def __init__(self, store: ProfileStore, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("配置方案管理")
        self.store = store
        self.list_widget = QListWidget()
        self.load_button = QPushButton("加载")
        self.delete_button = QPushButton("删除")
        self.import_button = QPushButton("导入")
        self.refresh_button = QPushButton("刷新")

        row = QHBoxLayout()
        for button in [self.refresh_button, self.import_button, self.load_button, self.delete_button]:
            row.addWidget(button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.list_widget)
        layout.addLayout(row)
        self.refresh_button.clicked.connect(self.refresh)
        self.load_button.clicked.connect(self.load_selected)
        self.delete_button.clicked.connect(self.delete_selected)
        self.import_button.clicked.connect(self.import_profile)
        self.refresh()

    def refresh(self) -> None:
        self.list_widget.clear()
        for path in self.store.list_profiles():
            self.list_widget.addItem(str(path))

    def load_selected(self) -> None:
        item = self.list_widget.currentItem()
        if item:
            self.profile_loaded.emit(self.store.load(item.text()))
            self.accept()

    def delete_selected(self) -> None:
        item = self.list_widget.currentItem()
        if item:
            self.store.delete(item.text())
            self.refresh()

    def import_profile(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "导入配置", "", "YAML (*.yaml *.yml)")
        if path:
            profile = self.store.load(path)
            self.store.save(profile)
            self.refresh()
