from __future__ import annotations

from dataclasses import dataclass
import time


@dataclass(slots=True)
class FireWaterLine:
    """One decoded FireWater text line.

    The parser intentionally stops here: it knows the optional prefix and
    numeric fields, but it does not infer physical channel meanings.
    """

    raw_line: str
    prefix: str
    values: list[float]
    timestamp: float
    valid: bool
    error: str | None = None
    is_image_packet: bool = False

    @classmethod
    def invalid(
        cls,
        raw_line: str,
        error: str,
        *,
        prefix: str = "",
        timestamp: float | None = None,
        is_image_packet: bool = False,
    ) -> "FireWaterLine":
        return cls(
            raw_line=raw_line,
            prefix=prefix,
            values=[],
            timestamp=time.time() if timestamp is None else timestamp,
            valid=False,
            error=error,
            is_image_packet=is_image_packet,
        )
