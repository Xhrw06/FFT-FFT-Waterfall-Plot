from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import yaml

from models.samples import PreprocessedSample
from models.spectrum import SpectrumFrame
from models.waterfall import WaterfallMatrix


class DataRecorder:
    """Writes one acquisition session folder."""

    def __init__(self, session_dir: str | Path, spectrum_chunk_size: int = 512) -> None:
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.spectrum_chunk_size = max(1, int(spectrum_chunk_size))
        self._sample_file = None
        self._sample_writer: csv.DictWriter | None = None
        self._sample_columns: list[str] = []
        self._spectra: list[SpectrumFrame] = []
        self._spectrum_chunk_paths: list[Path] = []

    @property
    def samples_path(self) -> Path:
        return self.session_dir / "samples.csv"

    def write_sample(self, sample: PreprocessedSample) -> None:
        row = self._sample_row(sample)
        if self._sample_writer is None:
            self._sample_columns = list(row.keys())
            self._sample_file = self.samples_path.open("w", newline="", encoding="utf-8")
            self._sample_writer = csv.DictWriter(self._sample_file, fieldnames=self._sample_columns)
            self._sample_writer.writeheader()
        else:
            for key in list(row.keys()):
                if key not in self._sample_columns:
                    # Keep the CSV stable during long runs; new dynamic channels
                    # are still available in the profile and spectrum exports.
                    row.pop(key, None)
        self._sample_writer.writerow(row)

    def append_spectrum(self, frame: SpectrumFrame) -> None:
        self._spectra.append(frame)
        if len(self._spectra) >= self.spectrum_chunk_size:
            self._flush_spectrum_chunk()

    def save_spectrum_npz(self, extra: dict | None = None) -> Path:
        self._flush_spectrum_chunk()
        path = self.session_dir / "spectrum.npz"
        if not self._spectrum_chunk_paths:
            np.savez(path, timestamps=np.array([]), throttle=np.array([]), freqs=np.array([]), db_frames=np.empty((0, 0)))
            return path
        chunk_groups = self._load_spectrum_chunk_groups()
        for group_index, chunks in enumerate(chunk_groups):
            target = path if group_index == 0 else self.session_dir / f"spectrum_{group_index:03d}.npz"
            payload = {
                "timestamps": np.concatenate([chunk["timestamps"] for chunk in chunks]),
                "throttle": np.concatenate([chunk["throttle"] for chunk in chunks]),
                "freqs": chunks[0]["freqs"],
                "db_frames": np.vstack([chunk["db_frames"] for chunk in chunks]),
                "analysis_channel": np.concatenate([chunk["analysis_channel"] for chunk in chunks]),
            }
            if extra:
                payload.update(extra)
            if len(chunk_groups) > 1:
                payload["frequency_group"] = group_index
                payload["frequency_group_count"] = len(chunk_groups)
            np.savez(target, **payload)
        for chunks in chunk_groups:
            for chunk in chunks:
                chunk.close()
        for chunk_path in self._spectrum_chunk_paths:
            try:
                chunk_path.unlink()
            except OSError:
                pass
        self._spectrum_chunk_paths.clear()
        return path

    def save_waterfall_npz(self, matrix: WaterfallMatrix) -> Path:
        path = self.session_dir / "waterfall.npz"
        np.savez(
            path,
            mode=matrix.mode,
            freq_axis=matrix.freq_axis,
            y_axis=matrix.y_axis,
            db_matrix=matrix.db_matrix,
            count_matrix=np.array([]) if matrix.count_matrix is None else matrix.count_matrix,
        )
        return path

    def save_yaml(self, name: str, data: dict) -> Path:
        path = self.session_dir / name
        with path.open("w", encoding="utf-8") as file:
            yaml.safe_dump(data, file, allow_unicode=True, sort_keys=False)
        return path

    def close(self) -> None:
        if self._sample_file is not None:
            self._sample_file.flush()
            self._sample_file.close()
            self._sample_file = None

    def _flush_spectrum_chunk(self) -> None:
        if not self._spectra:
            return
        groups: list[list[SpectrumFrame]] = []
        for frame in self._spectra:
            for group in groups:
                first = group[0]
                if frame.freqs.shape == first.freqs.shape and np.allclose(frame.freqs, first.freqs):
                    group.append(frame)
                    break
            else:
                groups.append([frame])
        for group in groups:
            self._write_spectrum_chunk(group)
        self._spectra.clear()

    def _write_spectrum_chunk(self, frames: list[SpectrumFrame]) -> None:
        if not frames:
            return
        first = frames[0]
        path = self.session_dir / f".spectrum_chunk_{len(self._spectrum_chunk_paths):05d}.npz"
        np.savez(
            path,
            timestamps=np.asarray([frame.center_timestamp for frame in frames]),
            throttle=np.asarray(
                [np.nan if frame.throttle_percent is None else frame.throttle_percent for frame in frames]
            ),
            freqs=first.freqs,
            db_frames=np.vstack([frame.db for frame in frames]),
            analysis_channel=np.asarray([frame.channel_name for frame in frames]),
        )
        self._spectrum_chunk_paths.append(path)

    def _load_spectrum_chunk_groups(self) -> list[list[np.lib.npyio.NpzFile]]:
        groups: list[list[np.lib.npyio.NpzFile]] = []
        for chunk_path in self._spectrum_chunk_paths:
            chunk = np.load(chunk_path, allow_pickle=False)
            for group in groups:
                freqs = group[0]["freqs"]
                if chunk["freqs"].shape == freqs.shape and np.allclose(chunk["freqs"], freqs):
                    group.append(chunk)
                    break
            else:
                groups.append([chunk])
        return groups

    @staticmethod
    def _sample_row(sample: PreprocessedSample) -> dict[str, float | str | None]:
        row: dict[str, float | str | None] = {
            "timestamp": sample.timestamp,
            "prefix": sample.prefix,
        }
        for channel in sorted(sample.raw_channels):
            row[f"{channel}_raw"] = sample.raw_channels.get(channel)
            row[f"{channel}_dc"] = sample.dc_estimates.get(channel)
            row[f"{channel}_ac"] = sample.ac_channels.get(channel)
        return row
