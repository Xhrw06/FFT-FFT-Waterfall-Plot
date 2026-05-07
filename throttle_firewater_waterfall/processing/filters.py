from __future__ import annotations

import numpy as np


def design_filter(
    filter_type: str,
    sample_rate: float,
    order: int,
    lowcut: float | None = None,
    highcut: float | None = None,
) -> dict[str, float | str | int | None]:
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    if filter_type == "highpass" and lowcut is None:
        raise ValueError("highpass requires lowcut")
    if filter_type == "lowpass" and highcut is None:
        raise ValueError("lowpass requires highcut")
    if filter_type == "bandpass" and (lowcut is None or highcut is None):
        raise ValueError("bandpass requires lowcut and highcut")
    if filter_type not in {"highpass", "lowpass", "bandpass"}:
        raise ValueError(f"unsupported filter type: {filter_type}")
    return {
        "type": filter_type,
        "sample_rate": float(sample_rate),
        "order": max(1, int(order)),
        "lowcut": None if lowcut is None else float(lowcut),
        "highcut": None if highcut is None else float(highcut),
    }


def apply_sos_filter(filter_config: dict[str, float | str | int | None], values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return values
    filter_type = str(filter_config["type"])
    output = values.copy()
    if filter_type in {"lowpass", "bandpass"}:
        output = _lowpass(output, float(filter_config["sample_rate"]), float(filter_config["highcut"]), int(filter_config["order"]))
    if filter_type in {"highpass", "bandpass"}:
        output = _highpass(output, float(filter_config["sample_rate"]), float(filter_config["lowcut"]), int(filter_config["order"]))
    return output


def _lowpass(values: np.ndarray, sample_rate: float, cutoff: float, order: int) -> np.ndarray:
    if cutoff <= 0 or cutoff >= sample_rate / 2:
        return values
    alpha = _lowpass_alpha(sample_rate, cutoff)
    output = values.copy()
    for _ in range(max(1, order)):
        previous = output[0]
        filtered = np.empty_like(output)
        for index, value in enumerate(output):
            previous = previous + alpha * (value - previous)
            filtered[index] = previous
        output = filtered
    return output


def _highpass(values: np.ndarray, sample_rate: float, cutoff: float, order: int) -> np.ndarray:
    if cutoff <= 0 or cutoff >= sample_rate / 2:
        return values
    alpha = _highpass_alpha(sample_rate, cutoff)
    output = values.copy()
    for _ in range(max(1, order)):
        previous_input = output[0]
        previous_output = 0.0
        filtered = np.empty_like(output)
        for index, value in enumerate(output):
            previous_output = alpha * (previous_output + value - previous_input)
            previous_input = value
            filtered[index] = previous_output
        output = filtered
    return output


def _lowpass_alpha(sample_rate: float, cutoff: float) -> float:
    dt = 1.0 / sample_rate
    rc = 1.0 / (2.0 * np.pi * cutoff)
    return dt / (rc + dt)


def _highpass_alpha(sample_rate: float, cutoff: float) -> float:
    dt = 1.0 / sample_rate
    rc = 1.0 / (2.0 * np.pi * cutoff)
    return rc / (rc + dt)
