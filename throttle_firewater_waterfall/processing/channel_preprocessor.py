from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import math

import numpy as np

from models.preprocess import PreprocessConfig
from models.samples import ChannelSample, PreprocessedSample


@dataclass
class _ChannelState:
    dc: float = 0.0
    initialized: bool = False
    last_value: float | None = None
    running_values: deque[tuple[float, float]] = field(default_factory=deque)
    highpass_prev_inputs: list[float] = field(default_factory=list)
    highpass_prev_outputs: list[float] = field(default_factory=list)


class ChannelPreprocessor:
    """Sample-by-sample preprocessing before FFT buffering.

    `window_mean` and `detrend` are fundamentally FFT-window operations, so this
    class records estimates and passes raw values through for those modes. The
    FFT analyzer then performs the window-level subtraction before windowing.
    """

    def __init__(self, config: PreprocessConfig) -> None:
        self.config = config
        self._states: dict[str, _ChannelState] = {}

    def update_config(self, config: PreprocessConfig) -> None:
        self.config = config
        self._states.clear()

    def process_sample(self, sample: ChannelSample) -> PreprocessedSample:
        raw_channels = dict(sample.channels)
        dc_estimates: dict[str, float] = {}
        ac_channels: dict[str, float | None] = {}
        flags = dict(sample.flags)

        for channel, value in sample.channels.items():
            if value is None:
                ac_channels[channel] = None
                continue

            numeric = float(value)
            state = self._states.setdefault(channel, _ChannelState())
            if not math.isfinite(numeric):
                if self.config.replace_nan_with_last and state.last_value is not None:
                    numeric = state.last_value
                    flags[channel] = "nan_replaced_with_last"
                else:
                    ac_channels[channel] = None
                    flags[channel] = "non_finite"
                    continue

            if self.config.clamp_outliers:
                limit = abs(self.config.outlier_abs_limit)
                if abs(numeric) > limit:
                    numeric = max(-limit, min(limit, numeric))
                    flags[channel] = "outlier_clamped"

            apply_dc = self._should_apply(channel, sample.roles.get(channel, "normal"))
            if self.config.dc_enabled and apply_dc:
                ac_value, dc_value = self._remove_dc(channel, numeric, sample.timestamp, state)
            else:
                ac_value, dc_value = numeric, 0.0

            if self.config.dc_warning_enabled and abs(dc_value) >= self.config.dc_warning_threshold_abs:
                flags[f"{channel}:dc_warning"] = f"dc_estimate={dc_value:.6g}"

            state.last_value = numeric
            dc_estimates[channel] = dc_value
            ac_channels[channel] = ac_value

        return PreprocessedSample(
            timestamp=sample.timestamp,
            prefix=sample.prefix,
            raw_channels=raw_channels,
            dc_estimates=dc_estimates,
            ac_channels=ac_channels,
            flags=flags,
        )

    def get_dc_estimate(self, channel_name: str) -> float | None:
        state = self._states.get(channel_name)
        if state is None or not state.initialized:
            return None
        return state.dc

    def reset_channel_state(self, channel_name: str) -> None:
        self._states.pop(channel_name, None)

    def _should_apply(self, channel: str, role: str) -> bool:
        if self.config.apply_channels and channel in self.config.apply_channels:
            return True
        if not self.config.apply_channels and role in self.config.apply_roles:
            return True
        return False

    def _remove_dc(
        self,
        channel: str,
        value: float,
        timestamp: float,
        state: _ChannelState,
    ) -> tuple[float, float]:
        mode = self.config.dc_mode
        if mode == "none":
            state.dc = 0.0
            state.initialized = True
            return value, state.dc

        if mode == "ema":
            alpha = max(0.0, min(1.0, float(self.config.ema_alpha)))
            if not state.initialized:
                state.dc = value
                state.initialized = True
            else:
                state.dc = alpha * value + (1.0 - alpha) * state.dc
            return value - state.dc, state.dc

        if mode == "running_mean":
            window_sec = max(1e-6, float(self.config.running_mean_window_sec))
            state.running_values.append((timestamp, value))
            while state.running_values and timestamp - state.running_values[0][0] > window_sec:
                state.running_values.popleft()
            values = [item[1] for item in state.running_values]
            state.dc = float(np.mean(values)) if values else value
            state.initialized = True
            return value - state.dc, state.dc

        if mode == "highpass":
            return self._highpass_step(value, state)

        if mode == "detrend":
            state.dc = value
            state.initialized = True
            return value, state.dc

        if mode == "window_mean":
            if not state.initialized:
                state.dc = value
                state.initialized = True
            else:
                alpha = max(0.001, min(0.5, float(self.config.ema_alpha)))
                state.dc = alpha * value + (1.0 - alpha) * state.dc
            return value, state.dc

        raise ValueError(f"unsupported dc_mode: {mode}")

    def _highpass_step(self, value: float, state: _ChannelState) -> tuple[float, float]:
        sample_rate = float(self.config.sample_rate)
        cutoff = float(self.config.highpass_cutoff_hz)
        if sample_rate <= 0 or cutoff <= 0 or cutoff >= sample_rate / 2:
            state.dc = 0.0
            state.initialized = True
            return value, state.dc
        order = max(1, int(self.config.highpass_order))
        if len(state.highpass_prev_inputs) != order:
            state.highpass_prev_inputs = [value] * order
            state.highpass_prev_outputs = [0.0] * order

        dt = 1.0 / sample_rate
        rc = 1.0 / (2.0 * math.pi * cutoff)
        alpha = rc / (rc + dt)
        stage_input = value
        for index in range(order):
            previous_input = state.highpass_prev_inputs[index]
            previous_output = state.highpass_prev_outputs[index]
            stage_output = alpha * (previous_output + stage_input - previous_input)
            state.highpass_prev_inputs[index] = stage_input
            state.highpass_prev_outputs[index] = stage_output
            stage_input = stage_output

        ac_value = float(stage_input)
        state.dc = value - ac_value
        state.initialized = True
        return ac_value, state.dc
