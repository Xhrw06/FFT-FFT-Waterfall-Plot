from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ChannelSample:
    """Named, scaled channels produced from a FireWaterLine by a GUI profile."""

    timestamp: float
    prefix: str
    channels: dict[str, float | None]
    raw_values: list[float]
    roles: dict[str, str] = field(default_factory=dict)
    units: dict[str, str] = field(default_factory=dict)
    flags: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class PreprocessedSample:
    timestamp: float
    prefix: str
    raw_channels: dict[str, float | None]
    dc_estimates: dict[str, float]
    ac_channels: dict[str, float | None]
    flags: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class ThrottleSample:
    timestamp: float
    throttle_percent: float
    raw_value: float | None
    channel_name: str
    stale: bool = False
