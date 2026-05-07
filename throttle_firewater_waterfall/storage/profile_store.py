from __future__ import annotations

from pathlib import Path

import yaml

from models.channel_mapping import ChannelMappingProfile


class ProfileStore:
    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def list_profiles(self) -> list[Path]:
        return sorted(self.directory.glob("*.yaml"))

    def save(self, profile: ChannelMappingProfile, filename: str | None = None) -> Path:
        name = filename or f"{profile.name}.yaml"
        path = self.directory / name
        with path.open("w", encoding="utf-8") as file:
            yaml.safe_dump(profile.to_dict(), file, allow_unicode=True, sort_keys=False)
        return path

    def load(self, path: str | Path) -> ChannelMappingProfile:
        target = Path(path)
        with target.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
        return ChannelMappingProfile.from_dict(data.get("name", target.stem), data)

    def delete(self, path: str | Path) -> None:
        Path(path).unlink(missing_ok=True)
