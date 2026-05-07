from __future__ import annotations

import time


def now_monotonic() -> float:
    return time.monotonic()


def now_wall() -> float:
    return time.time()
