from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import deque

from models.channel_mapping import ThrottleConfig
from models.samples import ChannelSample, ThrottleSample


class ThrottleAligner:
    """Maintains throttle history and aligns FFT windows by timestamp."""

    def __init__(self, config: ThrottleConfig, max_samples: int = 20000) -> None:
        self.config = config
        self.max_samples = max_samples
        self._samples: deque[ThrottleSample] = deque(maxlen=max_samples)
        self._smoothed: float | None = None

    def update_config(self, config: ThrottleConfig) -> None:
        self.config = config
        self.reset()

    def reset(self) -> None:
        self._samples.clear()
        self._smoothed = None

    def observe_channel_sample(self, sample: ChannelSample) -> ThrottleSample | None:
        channel = self.config.channel
        if channel not in sample.channels or sample.channels[channel] is None:
            for name, role in sample.roles.items():
                if role == "throttle" and sample.channels.get(name) is not None:
                    channel = name
                    break
            else:
                return None
        raw = float(sample.channels[channel])
        percent = self.config.normalize_value(raw)
        alpha = max(0.0, min(1.0, float(self.config.smoothing_alpha)))
        if self._smoothed is None:
            self._smoothed = percent
        else:
            self._smoothed = alpha * percent + (1.0 - alpha) * self._smoothed
        throttle_sample = ThrottleSample(
            timestamp=sample.timestamp,
            throttle_percent=float(self._smoothed),
            raw_value=raw,
            channel_name=channel,
            stale=False,
        )
        self._samples.append(throttle_sample)
        return throttle_sample

    def align(self, timestamp: float, mode: str = "nearest") -> ThrottleSample | None:
        if not self._samples:
            return None
        timestamps = [sample.timestamp for sample in self._samples]

        if mode == "previous":
            index = bisect_right(timestamps, timestamp) - 1
            if index < 0:
                return None
            selected = self._samples[index]
            return self._with_stale(selected, timestamp)

        if mode == "linear":
            right = bisect_left(timestamps, timestamp)
            if right <= 0:
                return self._with_stale(self._samples[0], timestamp)
            if right >= len(self._samples):
                return self._with_stale(self._samples[-1], timestamp)
            left_sample = self._samples[right - 1]
            right_sample = self._samples[right]
            span = right_sample.timestamp - left_sample.timestamp
            if span <= 0:
                return self._with_stale(left_sample, timestamp)
            ratio = (timestamp - left_sample.timestamp) / span
            percent = left_sample.throttle_percent + ratio * (
                right_sample.throttle_percent - left_sample.throttle_percent
            )
            raw = None
            if left_sample.raw_value is not None and right_sample.raw_value is not None:
                raw = left_sample.raw_value + ratio * (right_sample.raw_value - left_sample.raw_value)
            return ThrottleSample(
                timestamp=timestamp,
                throttle_percent=float(percent),
                raw_value=raw,
                channel_name=left_sample.channel_name,
                stale=max(timestamp - left_sample.timestamp, right_sample.timestamp - timestamp)
                > self.config.timeout_sec,
            )

        left = bisect_left(timestamps, timestamp)
        candidates = []
        if left < len(self._samples):
            candidates.append(self._samples[left])
        if left > 0:
            candidates.append(self._samples[left - 1])
        selected = min(candidates, key=lambda item: abs(item.timestamp - timestamp))
        return self._with_stale(selected, timestamp)

    def latest(self) -> ThrottleSample | None:
        return self._samples[-1] if self._samples else None

    def _with_stale(self, sample: ThrottleSample, timestamp: float) -> ThrottleSample:
        return ThrottleSample(
            timestamp=sample.timestamp,
            throttle_percent=sample.throttle_percent,
            raw_value=sample.raw_value,
            channel_name=sample.channel_name,
            stale=abs(timestamp - sample.timestamp) > self.config.timeout_sec,
        )
