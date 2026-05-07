from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass

from PySide6.QtCore import QThread, Signal

from protocol.firewater_parser import FireWaterParser


@dataclass(slots=True)
class SimulatorConfig:
    output_prefix: str = "imu"
    sample_rate: float = 1000.0
    throttle_period_sec: float = 20.0
    motor_base_hz: float = 20.0
    motor_gain_hz_per_percent: float = 3.0
    frame_resonance_hz: float = 85.0
    vacuum_hz: float = 145.0
    noise_std: float = 0.05
    dc_offset_gz: float = 10.0
    encoding: str = "ascii"

    @classmethod
    def from_dict(cls, data: dict) -> "SimulatorConfig":
        allowed = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in (data or {}).items() if k in allowed})


class SimulatorWorker(QThread):
    """Generates FireWater text bytes for no-hardware testing."""

    firewater_bytes = Signal(bytes)
    firewater_lines = Signal(list)
    stats_updated = Signal(dict)
    status_changed = Signal(str)

    def __init__(self, config: SimulatorConfig) -> None:
        super().__init__()
        self.config = config
        self._running = False
        self.parser = FireWaterParser(encoding=config.encoding)

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        self._running = True
        self.status_changed.emit("simulator_running")
        sample_rate = max(1.0, float(self.config.sample_rate))
        block_sec = 0.02
        block_samples = max(1, int(sample_rate * block_sec))
        sample_index = 0
        started = last_stats = time.time()
        rx_bytes = rx_lines = 0

        try:
            while self._running:
                now = time.time()
                lines_text: list[str] = []
                for _ in range(block_samples):
                    t = sample_index / sample_rate
                    lines_text.append(self._generate_line(t))
                    sample_index += 1
                payload = "".join(lines_text).encode(self.config.encoding, errors="replace")
                rx_bytes += len(payload)
                rx_lines += len(lines_text)
                self.firewater_bytes.emit(payload)
                parsed = self.parser.feed(payload, now)
                if parsed:
                    self.firewater_lines.emit(parsed)

                elapsed_work = time.time() - now
                sleep_time = max(0.0, block_sec - elapsed_work)
                if sleep_time:
                    self.msleep(int(sleep_time * 1000))

                current = time.time()
                if current - last_stats >= 0.5:
                    elapsed = max(current - started, 1e-6)
                    self.stats_updated.emit(
                        {
                            "connected": True,
                            "port": "SIM",
                            "baudrate": 0,
                            "rx_bytes": rx_bytes,
                            "rx_lines": rx_lines,
                            "valid_samples": rx_lines,
                            "byte_rate": rx_bytes / elapsed,
                            "line_rate": rx_lines / elapsed,
                            "sample_rate": rx_lines / elapsed,
                            "parse_errors": self.parser.parse_error_count,
                            "line_overflows": self.parser.line_overflow_count,
                            "buffer_length": self.parser.buffer_length,
                            "uptime_sec": current - started,
                        }
                    )
                    last_stats = current
        finally:
            self.status_changed.emit("simulator_stopped")
            self.stats_updated.emit({"connected": False, "port": "SIM"})

    def _generate_line(self, t: float) -> str:
        cfg = self.config
        phase = (t % cfg.throttle_period_sec) / cfg.throttle_period_sec
        triangle = 2.0 * phase if phase < 0.5 else 2.0 * (1.0 - phase)
        throttle = max(0.0, min(100.0, triangle * 100.0))
        f_motor = cfg.motor_base_hz + throttle * cfg.motor_gain_hz_per_percent
        frame_gain = 1.0 + 4.0 * math.exp(-((throttle - 45.0) ** 2) / (2.0 * 9.0**2))

        gz = cfg.dc_offset_gz
        gz += 1.0 * math.sin(2.0 * math.pi * f_motor * t)
        gz += 0.45 * math.sin(2.0 * math.pi * 2.0 * f_motor * t)
        gz += 0.22 * math.sin(2.0 * math.pi * 3.0 * f_motor * t)
        gz += 0.35 * frame_gain * math.sin(2.0 * math.pi * cfg.frame_resonance_hz * t)
        gz += 0.5 * math.sin(2.0 * math.pi * cfg.vacuum_hz * t)
        gz += random.gauss(0.0, cfg.noise_std)

        gx = 0.25 * math.sin(2.0 * math.pi * (f_motor * 0.8) * t) + random.gauss(0.0, cfg.noise_std)
        gy = 0.18 * math.sin(2.0 * math.pi * (f_motor * 1.2) * t) + random.gauss(0.0, cfg.noise_std)
        ax = 0.02 * math.sin(2.0 * math.pi * 8.0 * t) + random.gauss(0.0, 0.01)
        ay = 0.02 * math.sin(2.0 * math.pi * 10.0 * t) + random.gauss(0.0, 0.01)
        az = 1.0 + 0.03 * math.sin(2.0 * math.pi * cfg.frame_resonance_hz * t) + random.gauss(0.0, 0.01)

        values = [ax, ay, az, gx, gy, gz, throttle]
        csv = ",".join(f"{value:.6f}" for value in values)
        prefix = cfg.output_prefix.strip()
        return f"{prefix}:{csv}\n" if prefix else f"{csv}\n"
