from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

import numpy as np

from processing.peak_detector import PeakRecord


def export_peaks_csv(path: str | Path, records: Iterable[PeakRecord]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["timestamp", "throttle", "frequency", "db", "channel"])
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "timestamp": record.timestamp,
                    "throttle": record.throttle,
                    "frequency": record.frequency,
                    "db": record.db,
                    "channel": record.channel,
                }
            )
    return target


def export_markdown_report(path: str | Path, title: str, summary: dict) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {title}", ""]
    for key, value in summary.items():
        lines.append(f"- {key}: {value}")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def export_html_report(path: str | Path, title: str, summary: dict) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = "\n".join(f"<tr><th>{key}</th><td>{value}</td></tr>" for key, value in summary.items())
    target.write_text(
        f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title></head>"
        f"<body><h1>{title}</h1><table>{rows}</table></body></html>",
        encoding="utf-8",
    )
    return target


def save_matrix_csv(path: str | Path, matrix: np.ndarray) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    np.savetxt(target, matrix, delimiter=",")
    return target
