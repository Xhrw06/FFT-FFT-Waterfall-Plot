from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import yaml

from models.channel_mapping import (
    CHANNEL_ROLES,
    FFT_ROLES,
    ChannelMappingProfile,
    FieldMapping,
    PrefixMapping,
    ValidationMessage,
)
from models.firewater import FireWaterLine
from models.samples import ChannelSample


class ChannelMappingManager:
    """Apply GUI-defined channel mappings to FireWater raw values."""

    def __init__(
        self,
        profile: ChannelMappingProfile | None = None,
        *,
        allow_unknown_prefix: bool = True,
        extra_field_policy: str = "auto_name",
        missing_field_policy: str = "fill_none",
    ) -> None:
        self.profile = profile or ChannelMappingProfile()
        self.allow_unknown_prefix = allow_unknown_prefix
        self.extra_field_policy = extra_field_policy
        self.missing_field_policy = missing_field_policy
        self.observed_prefix_counts: dict[str, int] = {}
        self.last_raw_by_prefix: dict[str, FireWaterLine] = {}

    def apply_mapping(self, fw_line: FireWaterLine) -> ChannelSample | None:
        if not fw_line.valid or fw_line.is_image_packet:
            return None

        prefix = fw_line.prefix
        self.observed_prefix_counts[prefix] = self.observed_prefix_counts.get(prefix, 0) + 1
        self.last_raw_by_prefix[prefix] = fw_line

        prefix_mapping = self.profile.mappings.get(prefix)
        if prefix_mapping is None:
            if not self.allow_unknown_prefix:
                return None
            prefix_mapping = self._auto_prefix_mapping(prefix, len(fw_line.values))
        if not prefix_mapping.enabled or prefix_mapping.ignored:
            return None

        channels: dict[str, float | None] = {}
        roles: dict[str, str] = {}
        units: dict[str, str] = {}
        flags: dict[str, str] = {}

        configured_fields = {field.index: field for field in prefix_mapping.fields}
        max_index = max(len(fw_line.values), max(configured_fields.keys(), default=-1) + 1)

        for index in range(max_index):
            field = configured_fields.get(index)
            if field is None:
                if index >= len(fw_line.values):
                    continue
                if prefix_mapping.unknown_field_policy == "ignore" or self.extra_field_policy == "ignore":
                    continue
                field = self._auto_field(prefix, index)

            if not field.enabled or field.role == "ignore":
                continue

            raw_value = fw_line.values[index] if index < len(fw_line.values) else None
            if raw_value is None:
                if prefix_mapping.missing_field_policy == "fill_none" or self.missing_field_policy == "fill_none":
                    channels[field.name] = None
                    roles[field.name] = field.role
                    units[field.name] = field.unit
                    flags[field.name] = "missing"
                continue

            value = field.mapped_value(raw_value)
            range_flag = self._range_flag(field, value)
            if range_flag == "drop":
                continue
            if range_flag == "clamped_low":
                value = field.min_value if field.min_value is not None else value
            elif range_flag == "clamped_high":
                value = field.max_value if field.max_value is not None else value

            channels[field.name] = value
            roles[field.name] = field.role
            units[field.name] = field.unit
            if range_flag:
                flags[field.name] = range_flag

        if not channels:
            return None

        return ChannelSample(
            timestamp=fw_line.timestamp,
            prefix=prefix,
            channels=channels,
            raw_values=list(fw_line.values),
            roles=roles,
            units=units,
            flags=flags,
        )

    def get_known_prefixes(self) -> list[str]:
        prefixes = set(self.profile.mappings.keys())
        prefixes.update(self.observed_prefix_counts.keys())
        return sorted(prefixes, key=lambda item: (item != "", item))

    def update_prefix_mapping(self, prefix: str, mapping: PrefixMapping) -> None:
        self.profile.mappings[prefix] = mapping

    def validate_profile(self, profile: ChannelMappingProfile | None = None) -> list[ValidationMessage]:
        profile = profile or self.profile
        messages: list[ValidationMessage] = []
        has_throttle = False
        has_fft = False

        for prefix, prefix_mapping in profile.mappings.items():
            if prefix.lower() == "image":
                messages.append(
                    ValidationMessage(
                        "error",
                        "image prefix 是 FireWater 图片保留前缀，不能作为普通采样配置。",
                        prefix,
                        None,
                    )
                )
            if not prefix_mapping.enabled or prefix_mapping.ignored:
                continue

            seen_names: set[str] = set()
            for field in prefix_mapping.fields:
                if not field.enabled or field.role == "ignore":
                    continue
                if not field.name.strip():
                    messages.append(ValidationMessage("error", "通道名不能为空。", prefix, field.index))
                if field.name in seen_names:
                    messages.append(
                        ValidationMessage(
                            "error",
                            f"同一个 prefix 下通道名重复：{field.name}",
                            prefix,
                            field.index,
                        )
                    )
                seen_names.add(field.name)
                if field.role not in CHANNEL_ROLES:
                    messages.append(ValidationMessage("warning", f"未知角色：{field.role}", prefix, field.index))
                if field.role == "throttle":
                    has_throttle = True
                if field.role in FFT_ROLES:
                    has_fft = True
                if math.isnan(float(field.scale)):
                    messages.append(ValidationMessage("error", "scale 不能为 NaN。", prefix, field.index))
                if (
                    field.min_value is not None
                    and field.max_value is not None
                    and field.max_value < field.min_value
                ):
                    messages.append(ValidationMessage("warning", "最大合理值小于最小合理值。", prefix, field.index))

        if not has_throttle:
            messages.append(ValidationMessage("error", "油门瀑布图至少需要一个 throttle 通道。"))
        if not has_fft:
            messages.append(ValidationMessage("error", "FFT 至少需要一个 vibration、fft_primary 或 fft_optional 通道。"))
        if profile.throttle_config.input_max <= profile.throttle_config.input_min:
            messages.append(ValidationMessage("error", "油门输入最大值必须大于最小值。"))

        selected_fft = profile.fft_channel_config.selected_channels()
        if selected_fft and has_fft:
            mapped_fft = {
                field.name
                for prefix_mapping in profile.mappings.values()
                for field in prefix_mapping.fields
                if field.enabled and field.role in FFT_ROLES
            }
            missing_selected = [name for name in selected_fft if name not in mapped_fft]
            for channel in missing_selected:
                messages.append(ValidationMessage("warning", f"FFT 选择通道未在映射中标记为分析通道：{channel}"))

        return messages

    def save_profile(self, path: str) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as file:
            yaml.safe_dump(self.profile.to_dict(), file, allow_unicode=True, sort_keys=False)

    def load_profile(self, path: str) -> ChannelMappingProfile:
        with Path(path).open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
        profile = ChannelMappingProfile.from_dict(data.get("name", Path(path).stem), data)
        self.profile = profile
        return profile

    @staticmethod
    def load_profile_from_default_config(path: str) -> ChannelMappingProfile:
        with Path(path).open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
        mapping_cfg = data.get("channel_mapping", {})
        active_profile = mapping_cfg.get("active_profile", "default")
        profiles = mapping_cfg.get("profiles", {})
        profile_data = profiles.get(active_profile, {})
        return ChannelMappingProfile.from_dict(active_profile, profile_data)

    def _range_flag(self, field: FieldMapping, value: float) -> str:
        below = field.min_value is not None and value < field.min_value
        above = field.max_value is not None and value > field.max_value
        if not below and not above:
            return ""
        policy = field.out_of_range_policy
        if policy == "drop":
            return "drop"
        if policy == "clamp":
            return "clamped_low" if below else "clamped_high"
        if policy == "warn":
            return "range_warning_low" if below else "range_warning_high"
        return "range_ignored"

    @staticmethod
    def _auto_prefix_mapping(prefix: str, field_count: int) -> PrefixMapping:
        return PrefixMapping(
            prefix=prefix,
            display_name=prefix or "无前缀数据",
            fields=[ChannelMappingManager._auto_field(prefix, i) for i in range(field_count)],
            unknown_field_policy="auto_name",
            missing_field_policy="fill_none",
            enabled=True,
        )

    @staticmethod
    def _auto_field(prefix: str, index: int) -> FieldMapping:
        safe_prefix = prefix if prefix else "ch"
        name = f"{safe_prefix}_ch{index}" if prefix else f"ch{index}"
        return FieldMapping(index=index, name=name, role="normal", unit="")
