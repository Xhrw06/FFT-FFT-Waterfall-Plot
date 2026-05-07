from __future__ import annotations

import time
from dataclasses import dataclass

try:
    import serial
except ImportError:  # pragma: no cover
    serial = None  # type: ignore

from PySide6.QtCore import QThread, Signal

from protocol.firewater_parser import FireWaterParser


@dataclass(slots=True)
class SerialConfig:
    port: str = ""
    baudrate: int = 115200
    bytesize: int = 8
    parity: str = "N"
    stopbits: float = 1
    timeout: float = 0.02
    encoding: str = "ascii"
    max_line_length: int = 4096
    ignore_image_packet: bool = True


class SerialWorker(QThread):
    """Background serial reader that parses FireWater lines off the GUI thread."""

    firewater_lines = Signal(list)
    raw_bytes = Signal(bytes)
    stats_updated = Signal(dict)
    status_changed = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, config: SerialConfig) -> None:
        super().__init__()
        self.config = config
        self._running = False
        self._serial = None
        self.parser = FireWaterParser(
            encoding=config.encoding,
            max_line_length=config.max_line_length,
            ignore_image_packet=config.ignore_image_packet,
        )

    def stop(self) -> None:
        self._running = False
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception as exc:  # pragma: no cover - defensive shutdown path.
                self.error_occurred.emit(f"关闭串口失败：{exc}")

    def run(self) -> None:  # pragma: no cover - requires hardware.
        if serial is None:
            self.error_occurred.emit("未安装 pyserial，无法打开串口。")
            return
        if not self.config.port:
            self.error_occurred.emit("未选择串口。")
            return

        self._running = True
        started = last_stats = time.time()
        last_bytes = last_lines = last_valid = 0
        rx_bytes = rx_lines = valid_lines = 0
        try:
            self.status_changed.emit("opening")
            self._serial = serial.Serial(
                port=self.config.port,
                baudrate=self.config.baudrate,
                bytesize=self.config.bytesize,
                parity=self.config.parity,
                stopbits=self.config.stopbits,
                timeout=self.config.timeout,
            )
            self.status_changed.emit("connected")
            while self._running:
                chunk = self._serial.read(4096)
                if chunk:
                    now = time.time()
                    rx_bytes += len(chunk)
                    self.raw_bytes.emit(chunk)
                    lines = self.parser.feed(chunk, now)
                    if lines:
                        rx_lines += len(lines)
                        valid_lines += sum(1 for line in lines if line.valid)
                        self.firewater_lines.emit(lines)
                now = time.time()
                if now - last_stats >= 0.5:
                    elapsed = max(now - last_stats, 1e-6)
                    self.stats_updated.emit(
                        {
                            "connected": True,
                            "port": self.config.port,
                            "baudrate": self.config.baudrate,
                            "rx_bytes": rx_bytes,
                            "rx_lines": rx_lines,
                            "valid_samples": valid_lines,
                            "byte_rate": (rx_bytes - last_bytes) / elapsed,
                            "line_rate": (rx_lines - last_lines) / elapsed,
                            "sample_rate": (valid_lines - last_valid) / elapsed,
                            "parse_errors": self.parser.parse_error_count,
                            "line_overflows": self.parser.line_overflow_count,
                            "buffer_length": self.parser.buffer_length,
                            "uptime_sec": now - started,
                        }
                    )
                    last_stats = now
                    last_bytes = rx_bytes
                    last_lines = rx_lines
                    last_valid = valid_lines
        except Exception as exc:
            self.error_occurred.emit(f"串口错误：{exc}")
        finally:
            if self._serial is not None:
                try:
                    self._serial.close()
                except Exception as exc:
                    self.error_occurred.emit(f"关闭串口失败：{exc}")
            self.status_changed.emit("disconnected")
            self.stats_updated.emit({"connected": False, "port": self.config.port})
