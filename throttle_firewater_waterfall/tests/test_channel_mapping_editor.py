import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYQTGRAPH_QT_LIB", "PySide6")

from PySide6.QtWidgets import QApplication

from app.widgets.channel_mapping_editor import ChannelMappingEditor
from core.channel_mapping import ChannelMappingManager
from models.channel_mapping import ChannelMappingProfile
from protocol.firewater_parser import FireWaterParser


def app():
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication(sys.argv)
    return instance


def test_editor_focus_prefix_expands_t_gz_to_two_rows():
    app()
    manager = ChannelMappingManager(ChannelMappingProfile(name="test"))
    line = FireWaterParser().feed(b"t/gz:37,12.5\r\n")[0]
    editor = ChannelMappingEditor(manager)
    editor.focus_prefix("t/gz", line)
    assert editor.table.rowCount() == 2
    assert editor.table.item(0, 2).text() == "37"
    assert editor.table.item(1, 2).text() == "12.5"


def test_editor_preset_sets_throttle_and_gz_roles():
    app()
    manager = ChannelMappingManager(ChannelMappingProfile(name="test"))
    line = FireWaterParser().feed(b"t/gz:37,12.5\r\n")[0]
    editor = ChannelMappingEditor(manager)
    editor.focus_prefix("t/gz", line)
    editor._apply_throttle_gz_preset()
    fields = editor.table.fields()
    assert fields[0].name == "throttle"
    assert fields[0].role == "throttle"
    assert fields[1].name == "gz"
    assert fields[1].role == "fft_primary"
