from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class BufferSlice:
    timestamps: np.ndarray
    values: np.ndarray


class RingBuffer:
    """Fixed-size timestamp/value buffer."""

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = int(capacity)
        self._timestamps: deque[float] = deque(maxlen=self.capacity)
        self._values: deque[float] = deque(maxlen=self.capacity)

    def append(self, timestamp: float, value: float) -> None:
        self._timestamps.append(float(timestamp))
        self._values.append(float(value))

    def clear(self) -> None:
        self._timestamps.clear()
        self._values.clear()

    def __len__(self) -> int:
        return len(self._values)

    def latest(self) -> tuple[float, float] | None:
        if not self._values:
            return None
        return self._timestamps[-1], self._values[-1]

    def get_recent(self, count: int) -> BufferSlice:
        count = max(0, min(int(count), len(self._values)))
        if count == 0:
            return BufferSlice(np.array([], dtype=float), np.array([], dtype=float))
        return BufferSlice(
            np.asarray(list(self._timestamps)[-count:], dtype=float),
            np.asarray(list(self._values)[-count:], dtype=float),
        )

    def get_time_range(self, start_timestamp: float, end_timestamp: float) -> BufferSlice:
        timestamps = np.asarray(self._timestamps, dtype=float)
        values = np.asarray(self._values, dtype=float)
        if timestamps.size == 0:
            return BufferSlice(timestamps, values)
        mask = (timestamps >= start_timestamp) & (timestamps <= end_timestamp)
        return BufferSlice(timestamps[mask], values[mask])


class MultiChannelRingBuffer:
    """Fixed-size ring buffers keyed by channel name."""

    def __init__(self, capacity: int) -> None:
        self.capacity = int(capacity)
        self._buffers: dict[str, RingBuffer] = {}

    def append(self, channel: str, timestamp: float, value: float) -> None:
        self._buffers.setdefault(channel, RingBuffer(self.capacity)).append(timestamp, value)

    def get_channel(self, channel: str) -> RingBuffer:
        return self._buffers.setdefault(channel, RingBuffer(self.capacity))

    def channels(self) -> list[str]:
        return sorted(self._buffers.keys())

    def clear(self) -> None:
        self._buffers.clear()
