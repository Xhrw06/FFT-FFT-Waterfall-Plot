from __future__ import annotations

import time

from models.firewater import FireWaterLine
from protocol.firewater_defs import (
    DECODE_ERROR,
    DEFAULT_ENCODING,
    DEFAULT_MAX_LINE_LENGTH,
    EMPTY_LINE,
    FIREWATER_IMAGE_PREFIX,
    IMAGE_PACKET_IGNORED,
    LINE_STRIP_CHARS,
    LINE_TOO_LONG,
    NON_NUMERIC_FIELD,
    NO_VALUES,
)


class FireWaterParser:
    """Incremental parser for VOFA+ FireWater text data.

    FireWater is a newline-delimited, CSV-style text stream. This parser only
    converts bytes into a prefix plus raw numeric values. Channel semantics are
    deliberately handled later by ChannelMappingManager.
    """

    def __init__(
        self,
        encoding: str = DEFAULT_ENCODING,
        max_line_length: int = DEFAULT_MAX_LINE_LENGTH,
        ignore_image_packet: bool = True,
    ) -> None:
        self.encoding = encoding
        self.max_line_length = int(max_line_length)
        self.ignore_image_packet = ignore_image_packet
        self._buffer = bytearray()
        self.parse_error_count = 0
        self.line_overflow_count = 0
        self.image_packet_count = 0

    @property
    def buffer_length(self) -> int:
        return len(self._buffer)

    def feed(self, data: bytes, timestamp: float | None = None) -> list[FireWaterLine]:
        """Feed arbitrary bytes and return all complete FireWater lines."""

        if not data:
            return []

        self._buffer.extend(data)
        lines: list[FireWaterLine] = []

        while True:
            newline_index = self._buffer.find(b"\n")
            if newline_index < 0:
                if len(self._buffer) > self.max_line_length:
                    self._buffer.clear()
                    self.line_overflow_count += 1
                break

            raw_line_bytes = bytes(self._buffer[: newline_index + 1])
            del self._buffer[: newline_index + 1]
            if self._buffer.startswith(b"\r"):
                del self._buffer[:1]

            line_timestamp = time.time() if timestamp is None else timestamp
            if len(raw_line_bytes) > self.max_line_length:
                self.line_overflow_count += 1
                lines.append(
                    FireWaterLine.invalid(
                        "",
                        LINE_TOO_LONG,
                        timestamp=line_timestamp,
                    )
                )
                continue

            try:
                raw_line = raw_line_bytes.decode(self.encoding)
            except UnicodeDecodeError as exc:
                self.parse_error_count += 1
                lines.append(
                    FireWaterLine.invalid(
                        raw_line_bytes.decode(self.encoding, errors="replace"),
                        f"{DECODE_ERROR}: {exc}",
                        timestamp=line_timestamp,
                    )
                )
                continue

            line = self.parse_line(raw_line, line_timestamp)
            if line.error and not line.is_image_packet and line.error != EMPTY_LINE:
                self.parse_error_count += 1
            if line.is_image_packet:
                self.image_packet_count += 1
            lines.append(line)

        return lines

    def parse_line(self, line: str, timestamp: float) -> FireWaterLine:
        """Parse one stripped or unstripped FireWater text line."""

        cleaned = line.strip(LINE_STRIP_CHARS)
        if not cleaned:
            return FireWaterLine.invalid(line, EMPTY_LINE, timestamp=timestamp)

        if ":" in cleaned:
            prefix_part, values_part = cleaned.split(":", 1)
            prefix = prefix_part.strip()
        else:
            prefix = ""
            values_part = cleaned

        if prefix.lower() == FIREWATER_IMAGE_PREFIX:
            return FireWaterLine(
                raw_line=cleaned,
                prefix=prefix,
                values=[],
                timestamp=timestamp,
                valid=not self.ignore_image_packet,
                error=IMAGE_PACKET_IGNORED if self.ignore_image_packet else None,
                is_image_packet=True,
            )

        values_text = values_part.strip()
        if not values_text:
            return FireWaterLine.invalid(
                cleaned,
                NO_VALUES,
                prefix=prefix,
                timestamp=timestamp,
            )

        values: list[float] = []
        for index, item in enumerate(values_text.split(",")):
            token = item.strip()
            if token == "":
                return FireWaterLine.invalid(
                    cleaned,
                    f"{NON_NUMERIC_FIELD}[{index}]=''",
                    prefix=prefix,
                    timestamp=timestamp,
                )
            try:
                values.append(float(token))
            except ValueError:
                return FireWaterLine.invalid(
                    cleaned,
                    f"{NON_NUMERIC_FIELD}[{index}]='{token}'",
                    prefix=prefix,
                    timestamp=timestamp,
                )

        return FireWaterLine(
            raw_line=cleaned,
            prefix=prefix,
            values=values,
            timestamp=timestamp,
            valid=True,
            error=None,
            is_image_packet=False,
        )
