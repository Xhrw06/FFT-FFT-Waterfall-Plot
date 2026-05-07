try:
    from PySide6.QtCore import QObject, Signal
except ImportError:  # pragma: no cover - lets non-GUI tests import the module.
    QObject = object  # type: ignore

    class Signal:  # type: ignore
        def __init__(self, *args, **kwargs) -> None:
            pass


class EventBus(QObject):
    firewater_line = Signal(object)
    channel_sample = Signal(object)
    preprocessed_sample = Signal(object)
    spectrum_frame = Signal(object)
    waterfall_matrix = Signal(object)
    stats_updated = Signal(dict)
    warning = Signal(str)
