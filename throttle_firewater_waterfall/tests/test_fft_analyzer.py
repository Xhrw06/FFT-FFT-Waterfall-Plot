import numpy as np

from processing.fft_analyzer import FFTAnalyzer, FFTConfig


def test_single_sine_frequency_identification():
    fs = 1000
    n = 1024
    t = np.arange(n) / fs
    values = np.sin(2 * np.pi * 50 * t)
    frame = FFTAnalyzer(FFTConfig(sample_rate=fs, window_size=n, freq_max=200, ignore_below_hz=2)).analyze(values)
    peak = frame.freqs[np.argmax(frame.db)]
    assert abs(peak - 50) < fs / n


def test_dc_bias_removed():
    fs = 1000
    n = 1024
    t = np.arange(n) / fs
    values = 100 + np.sin(2 * np.pi * 60 * t)
    frame = FFTAnalyzer(FFTConfig(sample_rate=fs, window_size=n, freq_max=200, remove_dc=True)).analyze(values)
    assert frame.db[0] <= -100


def test_window_functions_supported():
    values = np.ones(256)
    for window in ["hann", "hamming", "blackman", "rectangular"]:
        frame = FFTAnalyzer(FFTConfig(window_size=256, window=window)).analyze(values)
        assert frame.freqs.size == frame.db.size


def test_overlap_hop_size():
    analyzer = FFTAnalyzer(FFTConfig(window_size=100, overlap=0.75))
    assert analyzer.hop_size == 25


def test_db_floor_and_ignore_below():
    frame = FFTAnalyzer(FFTConfig(window_size=256, db_floor=-80, ignore_below_hz=10)).analyze(np.zeros(256))
    assert frame.db.min() == -80
    assert np.all(frame.db[frame.freqs < 10] == -80)
