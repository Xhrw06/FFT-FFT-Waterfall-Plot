import numpy as np

from models.spectrum import SpectrumFrame
from storage.data_recorder import DataRecorder


def spectrum(freqs, db, timestamp=1.0, channel="gz"):
    freqs = np.asarray(freqs, dtype=float)
    db = np.asarray(db, dtype=float)
    return SpectrumFrame(
        timestamp=timestamp,
        center_timestamp=timestamp,
        throttle_percent=50.0,
        channel_name=channel,
        freqs=freqs,
        magnitude=np.ones_like(freqs),
        db=db,
    )


def test_spectrum_export_flushes_chunks(tmp_path):
    recorder = DataRecorder(tmp_path, spectrum_chunk_size=2)
    recorder.append_spectrum(spectrum([1, 2], [10, 20], timestamp=1))
    recorder.append_spectrum(spectrum([1, 2], [30, 40], timestamp=2))
    recorder.append_spectrum(spectrum([1, 2], [50, 60], timestamp=3))

    path = recorder.save_spectrum_npz()

    data = np.load(path, allow_pickle=False)
    assert data["timestamps"].tolist() == [1, 2, 3]
    assert data["db_frames"].tolist() == [[10, 20], [30, 40], [50, 60]]
    assert not list(tmp_path.glob(".spectrum_chunk_*.npz"))


def test_spectrum_export_splits_frequency_axis_changes(tmp_path):
    recorder = DataRecorder(tmp_path, spectrum_chunk_size=10)
    recorder.append_spectrum(spectrum([1, 2], [10, 20], timestamp=1))
    recorder.append_spectrum(spectrum([1, 2, 3], [30, 40, 50], timestamp=2))

    recorder.save_spectrum_npz()

    assert (tmp_path / "spectrum.npz").exists()
    assert (tmp_path / "spectrum_001.npz").exists()
