from __future__ import annotations

from pathlib import Path


class RawLogger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("ab")

    def write_bytes(self, data: bytes) -> None:
        self._file.write(data)

    def flush(self) -> None:
        self._file.flush()

    def close(self) -> None:
        self._file.flush()
        self._file.close()

    def __enter__(self) -> "RawLogger":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
