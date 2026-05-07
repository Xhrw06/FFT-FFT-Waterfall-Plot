from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class PreprocessConfig:
    dc_enabled: bool = True
    dc_mode: str = "window_mean"
    apply_channels: list[str] = field(default_factory=list)
    apply_roles: list[str] = field(
        default_factory=lambda: [
            "vibration",
            "fft_primary",
            "fft_optional",
            "imu_gyro",
            "imu_acc",
        ]
    )
    ema_alpha: float = 0.01
    running_mean_window_sec: float = 2.0
    highpass_cutoff_hz: float = 1.0
    highpass_order: int = 2
    sample_rate: float = 1000.0
    fft_remove_window_mean: bool = True
    detrend_enabled: bool = False
    replace_nan_with_last: bool = True
    clamp_outliers: bool = False
    outlier_abs_limit: float = 1.0e6
    dc_warning_enabled: bool = True
    dc_warning_threshold_abs: float = 5.0
    dc_warning_threshold_ratio: float = 0.5

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "PreprocessConfig":
        if not data:
            return cls()
        normalized = dict(data)
        if "apply_to_roles" in normalized and "apply_roles" not in normalized:
            normalized["apply_roles"] = normalized.pop("apply_to_roles")
        allowed = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in normalized.items() if k in allowed})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
