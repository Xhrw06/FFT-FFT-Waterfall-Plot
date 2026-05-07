import math

import numpy as np

from models.preprocess import PreprocessConfig
from models.samples import ChannelSample
from processing.channel_preprocessor import ChannelPreprocessor


def sample(value, t=0.0):
    return ChannelSample(t, "imu", {"gz": value}, [value], {"gz": "fft_primary"}, {"gz": "dps"}, {})


def test_none_mode():
    proc = ChannelPreprocessor(PreprocessConfig(dc_mode="none"))
    out = proc.process_sample(sample(10))
    assert out.ac_channels["gz"] == 10


def test_window_mean_passes_sample_and_estimates_dc():
    proc = ChannelPreprocessor(PreprocessConfig(dc_mode="window_mean", ema_alpha=0.5))
    proc.process_sample(sample(10, 0))
    out = proc.process_sample(sample(12, 1))
    assert out.ac_channels["gz"] == 12
    assert proc.get_dc_estimate("gz") == 11


def test_running_mean():
    proc = ChannelPreprocessor(PreprocessConfig(dc_mode="running_mean", running_mean_window_sec=10))
    proc.process_sample(sample(10, 0))
    out = proc.process_sample(sample(12, 1))
    assert out.dc_estimates["gz"] == 11
    assert out.ac_channels["gz"] == 1


def test_ema():
    proc = ChannelPreprocessor(PreprocessConfig(dc_mode="ema", ema_alpha=0.5))
    proc.process_sample(sample(10, 0))
    out = proc.process_sample(sample(12, 1))
    assert out.dc_estimates["gz"] == 11
    assert out.ac_channels["gz"] == 1


def test_highpass_removes_slow_dc():
    proc = ChannelPreprocessor(PreprocessConfig(dc_mode="highpass", highpass_cutoff_hz=1, sample_rate=100))
    outputs = []
    for i in range(300):
        out = proc.process_sample(sample(10.0, i / 100))
        outputs.append(out.ac_channels["gz"])
    assert abs(outputs[-1]) < 1.0


def test_detrend_mode_passes_sample():
    proc = ChannelPreprocessor(PreprocessConfig(dc_mode="detrend"))
    out = proc.process_sample(sample(10))
    assert out.ac_channels["gz"] == 10


def test_nan_handling():
    proc = ChannelPreprocessor(PreprocessConfig(dc_mode="none", replace_nan_with_last=True))
    proc.process_sample(sample(5))
    out = proc.process_sample(sample(float("nan")))
    assert out.ac_channels["gz"] == 5
    assert out.flags["gz"] == "nan_replaced_with_last"


def test_dc_warning():
    proc = ChannelPreprocessor(PreprocessConfig(dc_mode="ema", dc_warning_threshold_abs=5, ema_alpha=0.5))
    out = proc.process_sample(sample(10))
    assert "gz:dc_warning" in out.flags
