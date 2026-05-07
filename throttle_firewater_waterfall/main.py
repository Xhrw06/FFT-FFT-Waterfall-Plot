from __future__ import annotations

import sys
import os
from pathlib import Path

os.environ.setdefault("PYQTGRAPH_QT_LIB", "PySide6")

from PySide6.QtWidgets import QApplication

PROJECT_DIR = Path(__file__).resolve().parent

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from app.main_window import MainWindow
from utils.logger import setup_logging


def main() -> int:
    setup_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("throttle_firewater_waterfall")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
