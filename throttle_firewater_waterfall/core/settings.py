from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_config_path() -> Path:
    return project_root() / "config" / "default.yaml"


def load_yaml_config(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path else default_config_path()
    with target.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def save_yaml_config(path: str | Path, data: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as file:
        yaml.safe_dump(data, file, allow_unicode=True, sort_keys=False)
