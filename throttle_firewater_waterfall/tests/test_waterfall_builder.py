import numpy as np

from models.spectrum import SpectrumFrame
from processing.waterfall_builder import WaterfallBuilder, WaterfallConfig


def frame(db, throttle=10, t=0):
    freqs = np.array([0, 5, 10, 15], dtype=float)
    db = np.array(db, dtype=float)
    mag = np.ones_like(db)
    return SpectrumFrame(t, t, throttle, "gz", freqs, mag, db)


def test_time_waterfall_rolls():
    builder = WaterfallBuilder(WaterfallConfig(mode="time", time_rows=2, display_freq_min=0))
    builder.add_frame(frame([1, 2, 3, 4], t=1))
    matrix = builder.add_frame(frame([5, 6, 7, 8], t=2))
    matrix = builder.add_frame(frame([9, 10, 11, 12], t=3))
    assert matrix.db_matrix.tolist() == [[5, 6, 7, 8], [9, 10, 11, 12]]


def test_throttle_average():
    builder = WaterfallBuilder(WaterfallConfig(mode="throttle", aggregation="average", throttle_bin_size=10, display_freq_min=0))
    builder.add_frame(frame([10, 20, 30, 40], throttle=20))
    matrix = builder.add_frame(frame([20, 30, 40, 50], throttle=20))
    assert matrix.db_matrix[2].tolist() == [15, 25, 35, 45]
    assert matrix.count_matrix[2][0] == 2


def test_throttle_max_hold():
    builder = WaterfallBuilder(WaterfallConfig(mode="throttle", aggregation="max_hold", throttle_bin_size=10, display_freq_min=0))
    builder.add_frame(frame([10, 40, 30, 40], throttle=20))
    matrix = builder.add_frame(frame([20, 30, 50, 35], throttle=20))
    assert matrix.db_matrix[2].tolist() == [20, 40, 50, 40]


def test_throttle_ema():
    builder = WaterfallBuilder(WaterfallConfig(mode="throttle", aggregation="ema", ema_alpha=0.5, throttle_bin_size=10, display_freq_min=0))
    builder.add_frame(frame([10, 20, 30, 40], throttle=20))
    matrix = builder.add_frame(frame([20, 30, 40, 50], throttle=20))
    assert matrix.db_matrix[2].tolist() == [15, 25, 35, 45]


def test_display_freq_min_filters():
    builder = WaterfallBuilder(WaterfallConfig(mode="time", display_freq_min=5))
    matrix = builder.add_frame(frame([1, 2, 3, 4]))
    assert matrix.freq_axis.tolist() == [5, 10, 15]


def test_time_axis_rolls_after_config_update():
    builder = WaterfallBuilder(WaterfallConfig(mode="time", time_rows=3, display_freq_min=0))
    builder.add_frame(frame([1, 2, 3, 4], t=1))
    builder.add_frame(frame([5, 6, 7, 8], t=2))

    builder.update_config(WaterfallConfig(mode="time", time_rows=1, display_freq_min=0))
    matrix = builder.add_frame(frame([9, 10, 11, 12], t=3))

    assert matrix.y_axis.tolist() == [3]
    assert matrix.db_matrix.tolist() == [[9, 10, 11, 12]]
