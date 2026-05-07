from __future__ import annotations

from pathlib import Path
import time

from PySide6.QtCore import QThread, Signal

from protocol.firewater_parser import FireWaterParser


class ReplayWorker(QThread):
    firewater_bytes = Signal(bytes)
    firewater_lines = Signal(list)
    stats_updated = Signal(dict)
    status_changed = Signal(str)

    def __init__(self, raw_log_path: str | Path, speed: str = "1x", encoding: str = "ascii") -> None:
        super().__init__()
        self.raw_log_path = Path(raw_log_path)
        self.speed = speed
        self.encoding = encoding
        self._running = False
        self.parser = FireWaterParser(encoding=encoding)

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        if not self.raw_log_path.exists():
            self.status_changed.emit(f"回放文件不存在：{self.raw_log_path}")
            return
        self._running = True
        self.status_changed.emit("replay_running")
        delay = self._delay_sec()
        started = last_stats = time.time()
        rx_bytes = rx_lines = valid_lines = 0
        with self.raw_log_path.open("rb") as file:
            for raw_line in file:
                if not self._running:
                    break
                self.firewater_bytes.emit(raw_line)
                rx_bytes += len(raw_line)
                parsed = self.parser.feed(raw_line, time.time())
                if parsed:
                    rx_lines += len(parsed)
                    valid_lines += sum(1 for line in parsed if line.valid)
                    self.firewater_lines.emit(parsed)
                now = time.time()
                if now - last_stats >= 0.5:
                    elapsed = max(now - last_stats, 1e-6)
                    self.stats_updated.emit(
                        {
                            "connected": True,
                            "port": "REPLAY",
                            "baudrate": 0,
                            "rx_bytes": rx_bytes,
                            "rx_lines": rx_lines,
                            "valid_samples": valid_lines,
                            "byte_rate": rx_bytes / max(now - started, 1e-6),
                            "line_rate": rx_lines / max(now - started, 1e-6),
                            "sample_rate": valid_lines / max(now - started, 1e-6),
                            "parse_errors": self.parser.parse_error_count,
                            "line_overflows": self.parser.line_overflow_count,
                            "buffer_length": self.parser.buffer_length,
                            "uptime_sec": now - started,
                            "replay_rate_lines": rx_lines / elapsed,
                        }
                    )
                    last_stats = now
                if delay > 0:
                    self.msleep(int(delay * 1000))
        self.status_changed.emit("replay_stopped")
        self.stats_updated.emit({"connected": False, "port": "REPLAY"})

    def _delay_sec(self) -> float:
        if self.speed == "as_fast_as_possible":
            return 0.0
        mapping = {"0.5x": 0.002, "1x": 0.001, "2x": 0.0005}
        return mapping.get(self.speed, 0.001)
