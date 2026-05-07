from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class RuntimeStats:
    connected: bool = False
    running: bool = False
    port: str = ""
    baudrate: int = 115200
    rx_bytes: int = 0
    rx_lines: int = 0
    valid_samples: int = 0
    parse_errors: int = 0
    line_overflows: int = 0
    byte_rate: float = 0.0
    line_rate: float = 0.0
    sample_rate: float = 0.0
    buffer_length: int = 0
    uptime_sec: float = 0.0
    latest_warning: str = ""


@dataclass(slots=True)
class AppState:
    active_profile_name: str = "default_imu"
    current_prefix: str = ""
    latest_raw_line: str = ""
    latest_field_count: int = 0
    current_throttle_percent: float | None = None
    current_throttle_raw: float | None = None
    current_throttle_bin: int | None = None
    current_fft_channel: str = "gz"
    stats: RuntimeStats = field(default_factory=RuntimeStats)
