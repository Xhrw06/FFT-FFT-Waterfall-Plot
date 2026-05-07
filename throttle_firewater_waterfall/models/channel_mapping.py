from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from typing import Any


CHANNEL_ROLES = (
    "ignore",
    "normal",
    "throttle",
    "vibration",
    "imu_acc",
    "imu_gyro",
    "fft_primary",
    "fft_optional",
    "rpm",
    "temperature",
    "voltage",
    "current",
    "custom",
)

OUT_OF_RANGE_POLICIES = ("ignore", "warn", "clamp", "drop")
UNKNOWN_FIELD_POLICIES = ("ignore", "auto_name")
MISSING_FIELD_POLICIES = ("ignore", "fill_none")
FFT_ROLES = {"vibration", "fft_primary", "fft_optional"}


@dataclass(slots=True)
class FieldMapping:
    index: int
    name: str
    role: str = "normal"
    unit: str = ""
    enabled: bool = True
    scale: float = 1.0
    offset: float = 0.0
    decimals: int = 3
    min_value: float | None = None
    max_value: float | None = None
    out_of_range_policy: str = "warn"
    note: str = ""
    save_enabled: bool = True
    realtime_enabled: bool = True
    waterfall_enabled: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FieldMapping":
        allowed = {f.name for f in cls.__dataclass_fields__.values()}
        kwargs = {k: v for k, v in data.items() if k in allowed}
        return cls(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def mapped_value(self, raw_value: float) -> float:
        return raw_value * self.scale + self.offset


@dataclass(slots=True)
class PrefixMapping:
    prefix: str
    display_name: str = ""
    fields: list[FieldMapping] = field(default_factory=list)
    unknown_field_policy: str = "auto_name"
    missing_field_policy: str = "fill_none"
    enabled: bool = True
    ignored: bool = False

    @classmethod
    def from_dict(cls, prefix: str, data: dict[str, Any]) -> "PrefixMapping":
        fields = [FieldMapping.from_dict(item) for item in data.get("fields", [])]
        return cls(
            prefix=str(data.get("prefix", prefix)),
            display_name=str(data.get("display_name", prefix or "无前缀数据")),
            fields=fields,
            unknown_field_policy=str(data.get("unknown_field_policy", "auto_name")),
            missing_field_policy=str(data.get("missing_field_policy", "fill_none")),
            enabled=bool(data.get("enabled", True)),
            ignored=bool(data.get("ignored", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "prefix": self.prefix,
            "display_name": self.display_name,
            "fields": [field_mapping.to_dict() for field_mapping in self.fields],
            "unknown_field_policy": self.unknown_field_policy,
            "missing_field_policy": self.missing_field_policy,
            "enabled": self.enabled,
            "ignored": self.ignored,
        }

    @property
    def display_label(self) -> str:
        return self.display_name or self.prefix or "无前缀数据"


@dataclass(slots=True)
class ThrottleConfig:
    channel: str = "throttle"
    unit: str = "%"
    normalize: bool = True
    input_min: float = 0.0
    input_max: float = 100.0
    output_min: float = 0.0
    output_max: float = 100.0
    reverse: bool = False
    deadband: float = 0.0
    smoothing_alpha: float = 0.2
    timeout_sec: float = 1.0
    out_of_range_policy: str = "clamp"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ThrottleConfig":
        if not data:
            return cls()
        allowed = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in allowed})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def normalize_value(self, raw_value: float) -> float:
        if self.normalize:
            span = self.input_max - self.input_min
            if span <= 0 or math.isnan(span):
                raise ValueError("throttle input_max must be greater than input_min")
            pct = (raw_value - self.input_min) / span
            mapped = self.output_min + pct * (self.output_max - self.output_min)
        else:
            mapped = raw_value
        if self.reverse:
            mapped = self.output_max - (mapped - self.output_min)
        if abs(mapped) < self.deadband:
            mapped = 0.0
        if self.out_of_range_policy == "clamp":
            lo, hi = sorted((self.output_min, self.output_max))
            mapped = max(lo, min(hi, mapped))
        return mapped


@dataclass(slots=True)
class FFTChannelConfig:
    primary: str = "gz"
    optional: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "FFTChannelConfig":
        if not data:
            return cls()
        return cls(
            primary=str(data.get("primary", "gz")),
            optional=[str(item) for item in data.get("optional", [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def selected_channels(self) -> list[str]:
        channels = [self.primary] if self.primary else []
        channels.extend(ch for ch in self.optional if ch and ch not in channels)
        return channels


@dataclass(slots=True)
class ChannelMappingProfile:
    name: str = "default"
    description: str = ""
    mappings: dict[str, PrefixMapping] = field(default_factory=dict)
    throttle_config: ThrottleConfig = field(default_factory=ThrottleConfig)
    fft_channel_config: FFTChannelConfig = field(default_factory=FFTChannelConfig)

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> "ChannelMappingProfile":
        mappings_data = data.get("mappings", {})
        mappings = {
            str(prefix): PrefixMapping.from_dict(str(prefix), mapping_data or {})
            for prefix, mapping_data in mappings_data.items()
        }
        return cls(
            name=str(data.get("name", name)),
            description=str(data.get("description", "")),
            mappings=mappings,
            throttle_config=ThrottleConfig.from_dict(
                data.get("throttle_config", data.get("throttle", {}))
            ),
            fft_channel_config=FFTChannelConfig.from_dict(
                data.get("fft_channel_config", data.get("fft_channels", {}))
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "mappings": {key: value.to_dict() for key, value in self.mappings.items()},
            "throttle": self.throttle_config.to_dict(),
            "fft_channels": self.fft_channel_config.to_dict(),
        }


@dataclass(slots=True)
class ValidationMessage:
    level: str
    message: str
    prefix: str | None = None
    field_index: int | None = None
