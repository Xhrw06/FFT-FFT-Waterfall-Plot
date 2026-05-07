from __future__ import annotations

from pathlib import Path
import os
import time

os.environ.setdefault("PYQTGRAPH_QT_LIB", "PySide6")

import numpy as np
import yaml
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.dialogs.channel_mapping_wizard import ChannelMappingWizard
from app.widgets.acquisition_panel import AcquisitionPanel
from app.widgets.channel_mapping_editor import ChannelMappingEditor
from app.widgets.fft_panel import FFTPanel
from app.widgets.peak_panel import PeakPanel
from app.widgets.preprocess_panel import PreprocessPanel
from app.widgets.protocol_panel import ProtocolPanel
from app.widgets.serial_panel import SerialPanel
from app.widgets.spectrum_view import SpectrumView
from app.widgets.status_bar import AppStatusBar
from app.widgets.throttle_view import ThrottleView
from app.widgets.waterfall_view import WaterfallView
from core.channel_mapping import ChannelMappingManager
from core.settings import default_config_path, load_yaml_config
from models.channel_mapping import ChannelMappingProfile, FieldMapping, PrefixMapping
from models.firewater import FireWaterLine
from models.preprocess import PreprocessConfig
from models.samples import ChannelSample, PreprocessedSample
from models.spectrum import SpectrumFrame
from processing.channel_preprocessor import ChannelPreprocessor
from processing.fft_analyzer import FFTAnalyzer, FFTConfig
from processing.peak_detector import PeakDetector
from processing.ring_buffer import MultiChannelRingBuffer
from processing.throttle_aligner import ThrottleAligner
from processing.waterfall_builder import WaterfallBuilder, WaterfallConfig
from serial_io.serial_worker import SerialConfig, SerialWorker
from serial_io.simulator_worker import SimulatorConfig, SimulatorWorker
from storage.raw_logger import RawLogger
from storage.data_recorder import DataRecorder
from storage.replay_loader import ReplayWorker


class MainWindow(QMainWindow):
    """Main Qt shell that wires IO, mapping, processing and plotting."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("throttle_firewater_waterfall")
        self.resize(1500, 920)
        pg_configured = False
        try:
            import pyqtgraph as pg

            pg.setConfigOptions(antialias=True)
            pg_configured = True
        except Exception:
            pg_configured = False

        self.config = load_yaml_config(default_config_path())
        self.profile = self._load_profile_from_config(self.config)
        self.mapping_manager = ChannelMappingManager(
            self.profile,
            allow_unknown_prefix=self.config.get("protocol", {}).get("allow_unknown_prefix", True),
            extra_field_policy=self.config.get("protocol", {}).get("extra_field_policy", "auto_name"),
            missing_field_policy=self.config.get("protocol", {}).get("missing_field_policy", "fill_none"),
        )
        self.preprocess_config = PreprocessConfig.from_dict(self.config.get("preprocess", {}))
        self.preprocessor = ChannelPreprocessor(self.preprocess_config)
        self.throttle_aligner = ThrottleAligner(self.profile.throttle_config)
        self.fft_config = self._fft_config_from_yaml()
        self.fft_analyzer = FFTAnalyzer(self.fft_config)
        self.waterfall_config = self._waterfall_config_from_yaml()
        self.waterfall_builder = WaterfallBuilder(self.waterfall_config)
        self.peak_detector = PeakDetector(self._peak_config_from_yaml())
        self.buffers = MultiChannelRingBuffer(max(8192, self.fft_config.window_size * 8))
        self._sample_counter_by_channel: dict[str, int] = {}
        self._latest_spectrum: SpectrumFrame | None = None
        self._latest_waterfall = None
        self._latest_throttle = None
        self._serial_worker: SerialWorker | None = None
        self._sim_worker: SimulatorWorker | None = None
        self._replay_worker: ReplayWorker | None = None
        self._raw_logger: RawLogger | None = None
        self._data_recorder: DataRecorder | None = None
        self._mapping_editor: ChannelMappingEditor | None = None
        self._prompted_unknown_prefixes: set[str] = set()
        self._last_ui_update = 0.0

        self.serial_panel = SerialPanel()
        self.protocol_panel = ProtocolPanel()
        self.acquisition_panel = AcquisitionPanel()
        self.preprocess_panel = PreprocessPanel()
        self.fft_panel = FFTPanel()
        self.peak_panel = PeakPanel()
        self.waterfall_view = WaterfallView()
        self.spectrum_view = SpectrumView()
        self.throttle_view = ThrottleView()
        self.status = AppStatusBar()
        self.setStatusBar(self.status)

        self._apply_config_to_widgets()
        self._build_toolbar()
        self._build_layout()
        self._connect_widgets()

        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self._refresh_ui)
        fps = max(1, int(self.config.get("ui", {}).get("refresh_fps", 25)))
        self.ui_timer.start(int(1000 / fps))
        self.status.set_runtime("就绪。打开模拟数据模式即可无硬件运行。")

    def closeEvent(self, event) -> None:
        self._stop_workers()
        self._close_recording()
        super().closeEvent(event)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("工具栏")
        toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        self.open_action = QAction("打开串口", self)
        self.close_action = QAction("关闭串口", self)
        self.start_action = QAction("开始采集", self)
        self.pause_action = QAction("暂停采集", self)
        self.stop_action = QAction("停止采集", self)
        self.save_action = QAction("保存数据", self)
        self.load_replay_action = QAction("加载回放", self)
        self.mapping_action = QAction("打开通道映射", self)
        self.wizard_action = QAction("快速配置向导", self)

        for action in [
            self.open_action,
            self.close_action,
            self.start_action,
            self.pause_action,
            self.stop_action,
            self.save_action,
            self.load_replay_action,
            self.mapping_action,
            self.wizard_action,
        ]:
            toolbar.addAction(action)

        self.open_action.triggered.connect(lambda: self._open_serial(self.serial_panel.serial_config()))
        self.close_action.triggered.connect(self._close_serial)
        self.start_action.triggered.connect(self._start_selected_source)
        self.pause_action.triggered.connect(self._pause_acquisition)
        self.stop_action.triggered.connect(self._stop_workers)
        self.save_action.triggered.connect(self._toggle_raw_logging)
        self.load_replay_action.triggered.connect(self._load_replay)
        self.mapping_action.triggered.connect(self._open_mapping_editor)
        self.wizard_action.triggered.connect(self._open_wizard)

    def _build_layout(self) -> None:
        left_content = QWidget()
        left_layout = QVBoxLayout(left_content)
        left_layout.addWidget(self.serial_panel)
        left_layout.addWidget(self._stats_group())
        left_layout.addWidget(self.protocol_panel)
        left_layout.addWidget(self._channel_status_group())
        left_layout.addWidget(self._throttle_status_group())
        left_layout.addWidget(self.preprocess_panel)
        left_layout.addWidget(self.fft_panel)
        left_layout.addWidget(self._waterfall_panel())
        left_layout.addWidget(self.peak_panel)
        left_layout.addStretch(1)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setWidget(left_content)
        left_scroll.setMinimumWidth(360)

        lower_tabs = QTabWidget()
        lower_tabs.addTab(self.spectrum_view, "实时频谱")
        lower_tabs.addTab(self.throttle_view, "油门曲线")

        right_split = QSplitter(Qt.Orientation.Vertical)
        right_split.addWidget(self.waterfall_view)
        right_split.addWidget(lower_tabs)
        right_split.setSizes([650, 260])

        splitter = QSplitter()
        splitter.addWidget(left_scroll)
        splitter.addWidget(right_split)
        splitter.setSizes([380, 1120])

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(splitter)
        self.setCentralWidget(container)

    def _connect_widgets(self) -> None:
        self.serial_panel.open_requested.connect(self._open_serial)
        self.serial_panel.close_requested.connect(self._close_serial)
        self.serial_panel.simulator_toggled.connect(self._simulator_toggled)
        self.preprocess_panel.config_changed.connect(self._update_preprocess_config)
        self.fft_panel.config_changed.connect(self._update_fft_config)
        self.peak_panel.config_changed.connect(self.peak_detector.update_config)

    def _stats_group(self) -> QGroupBox:
        group = QGroupBox("串口状态")
        form = QFormLayout(group)
        self.stat_connection = QLabel("未连接")
        self.stat_port = QLabel("-")
        self.stat_byte_rate = QLabel("0 B/s")
        self.stat_line_rate = QLabel("0 line/s")
        self.stat_sample_rate = QLabel("0 sample/s")
        self.stat_errors = QLabel("0")
        self.stat_overflow = QLabel("0")
        self.stat_buffer = QLabel("0")
        self.stat_uptime = QLabel("0 s")
        form.addRow("连接状态", self.stat_connection)
        form.addRow("当前端口", self.stat_port)
        form.addRow("接收字节速率", self.stat_byte_rate)
        form.addRow("接收行率", self.stat_line_rate)
        form.addRow("有效采样率", self.stat_sample_rate)
        form.addRow("解析错误数", self.stat_errors)
        form.addRow("行溢出数", self.stat_overflow)
        form.addRow("缓冲区长度", self.stat_buffer)
        form.addRow("运行时间", self.stat_uptime)
        return group

    def _channel_status_group(self) -> QGroupBox:
        group = QGroupBox("通道配置")
        form = QFormLayout(group)
        self.profile_label = QLabel(self.profile.name)
        self.throttle_channel_label = QLabel(self.profile.throttle_config.channel)
        self.fft_channel_label = QLabel(self.profile.fft_channel_config.primary)
        self.config_status_label = QLabel("已加载")
        self.open_mapping_button = QPushButton("打开通道映射")
        self.open_wizard_button = QPushButton("快速配置向导")
        self.open_mapping_button.clicked.connect(self._open_mapping_editor)
        self.open_wizard_button.clicked.connect(self._open_wizard)
        form.addRow("当前配置方案", self.profile_label)
        form.addRow("当前油门通道", self.throttle_channel_label)
        form.addRow("当前 FFT 通道", self.fft_channel_label)
        form.addRow("配置状态", self.config_status_label)
        form.addRow("", self.open_mapping_button)
        form.addRow("", self.open_wizard_button)
        return group

    def _throttle_status_group(self) -> QGroupBox:
        group = QGroupBox("油门状态")
        form = QFormLayout(group)
        self.throttle_percent_label = QLabel("-")
        self.throttle_raw_label = QLabel("-")
        self.throttle_stale_label = QLabel("-")
        self.throttle_bin_label = QLabel("-")
        form.addRow("当前油门百分比", self.throttle_percent_label)
        form.addRow("原始油门值", self.throttle_raw_label)
        form.addRow("油门是否超时", self.throttle_stale_label)
        form.addRow("当前油门 bin", self.throttle_bin_label)
        return group

    def _waterfall_panel(self) -> QGroupBox:
        group = QGroupBox("瀑布图参数")
        form = QFormLayout(group)
        self.waterfall_mode_combo = QComboBox()
        self.waterfall_mode_combo.addItems(["throttle", "time"])
        self.waterfall_mode_combo.setCurrentText(self.waterfall_config.mode)
        self.db_min_spin = QDoubleSpinBox()
        self.db_min_spin.setRange(-240, 100)
        self.db_min_spin.setValue(self.waterfall_config.db_min)
        self.db_max_spin = QDoubleSpinBox()
        self.db_max_spin.setRange(-240, 100)
        self.db_max_spin.setValue(self.waterfall_config.db_max)
        self.aggregation_combo = QComboBox()
        self.aggregation_combo.addItems(["ema", "average", "max_hold"])
        self.aggregation_combo.setCurrentText(self.waterfall_config.aggregation)
        self.bin_spin = QDoubleSpinBox()
        self.bin_spin.setRange(0.5, 20)
        self.bin_spin.setValue(self.waterfall_config.throttle_bin_size)
        form.addRow("模式", self.waterfall_mode_combo)
        form.addRow("dB 最小值", self.db_min_spin)
        form.addRow("dB 最大值", self.db_max_spin)
        form.addRow("聚合方式", self.aggregation_combo)
        form.addRow("油门 bin 大小", self.bin_spin)
        for widget in [self.waterfall_mode_combo, self.db_min_spin, self.db_max_spin, self.aggregation_combo, self.bin_spin]:
            signal = getattr(widget, "currentTextChanged", None) or getattr(widget, "valueChanged")
            signal.connect(self._update_waterfall_config)
        return group

    def _start_selected_source(self) -> None:
        if self.serial_panel.simulator_check.isChecked():
            self._start_simulator()
        else:
            self._open_serial(self.serial_panel.serial_config())

    def _simulator_toggled(self, checked: bool) -> None:
        if checked:
            self._start_simulator()
        else:
            self._stop_simulator()

    def _start_simulator(self) -> None:
        self._close_serial()
        self._stop_replay()
        if self._sim_worker and self._sim_worker.isRunning():
            return
        self._reset_analysis_state()
        cfg = SimulatorConfig.from_dict(self.config.get("simulator", {}))
        cfg.sample_rate = self.fft_panel.sample_rate_spin.value()
        self._sim_worker = SimulatorWorker(cfg)
        self._sim_worker.firewater_bytes.connect(self._log_raw_bytes)
        self._sim_worker.firewater_lines.connect(self._handle_firewater_lines)
        self._sim_worker.stats_updated.connect(self._update_stats)
        self._sim_worker.status_changed.connect(self.status.set_runtime)
        self._sim_worker.start()
        self.status.set_runtime("模拟数据运行中")

    def _stop_simulator(self) -> None:
        if self._sim_worker:
            self._sim_worker.stop()
            self._sim_worker.wait(1500)
            self._sim_worker = None

    def _open_serial(self, config: SerialConfig) -> None:
        if self.serial_panel.simulator_check.isChecked():
            self._start_simulator()
            return
        self._stop_simulator()
        self._stop_replay()
        if self._serial_worker and self._serial_worker.isRunning():
            return
        if not config.port:
            QMessageBox.information(self, "串口", "请先选择串口，或启用模拟数据模式。")
            return
        self._reset_analysis_state()
        protocol_cfg = self.config.get("protocol", {})
        config.encoding = protocol_cfg.get("encoding", "ascii")
        config.max_line_length = protocol_cfg.get("max_line_length", 4096)
        config.ignore_image_packet = protocol_cfg.get("ignore_image_packet", True)
        self._serial_worker = SerialWorker(config)
        self._serial_worker.raw_bytes.connect(self._log_raw_bytes)
        self._serial_worker.firewater_lines.connect(self._handle_firewater_lines)
        self._serial_worker.stats_updated.connect(self._update_stats)
        self._serial_worker.status_changed.connect(self.status.set_runtime)
        self._serial_worker.error_occurred.connect(self._warn)
        self._serial_worker.start()

    def _close_serial(self) -> None:
        if self._serial_worker:
            self._serial_worker.stop()
            self._serial_worker.wait(1500)
            self._serial_worker = None

    def _stop_workers(self) -> None:
        self._close_serial()
        self._stop_simulator()
        self._stop_replay()
        self.status.set_runtime("已停止")

    def _pause_acquisition(self) -> None:
        self._close_serial()
        self._stop_simulator()
        self._stop_replay()
        self.status.set_runtime("已暂停")

    def _load_replay(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "加载 FireWater 回放",
            "",
            "FireWater logs (*.log *.txt *.csv);;All files (*)",
        )
        if not path:
            return
        self._close_serial()
        self._stop_simulator()
        self._stop_replay()
        self._reset_analysis_state()
        self._replay_worker = ReplayWorker(path)
        self._replay_worker.firewater_bytes.connect(self._log_raw_bytes)
        self._replay_worker.firewater_lines.connect(self._handle_firewater_lines)
        self._replay_worker.stats_updated.connect(self._update_stats)
        self._replay_worker.status_changed.connect(self.status.set_runtime)
        self._replay_worker.start()
        self.status.set_runtime(f"回放中: {Path(path).name}")

    def _stop_replay(self) -> None:
        if self._replay_worker:
            self._replay_worker.stop()
            self._replay_worker.wait(1500)
            self._replay_worker = None

    def _reset_analysis_state(self) -> None:
        self.buffers.clear()
        self.waterfall_builder.reset()
        self.throttle_aligner.reset()
        self._sample_counter_by_channel.clear()
        self._latest_spectrum = None
        self._latest_waterfall = None
        self._latest_throttle = None
        self.peak_detector.records.clear()
        self.spectrum_view.clear()
        self.waterfall_view.clear()
        self.throttle_view.clear()

    def _handle_firewater_lines(self, lines: list[FireWaterLine]) -> None:
        for line in lines:
            if self._mapping_editor:
                self._mapping_editor.observe_line(line)
            if line.is_image_packet:
                self._warn("收到 image: 数据，已按默认策略忽略。")
                continue
            if not line.valid:
                continue
            self.mapping_manager.last_raw_by_prefix[line.prefix] = line
            self.mapping_manager.observed_prefix_counts[line.prefix] = max(
                1,
                self.mapping_manager.observed_prefix_counts.get(line.prefix, 0),
            )
            configured = line.prefix in self.mapping_manager.profile.mappings
            self.protocol_panel.update_line(line, self.mapping_manager.get_known_prefixes(), configured)
            if not configured:
                self._handle_unknown_prefix(line)
            channel_sample = self.mapping_manager.apply_mapping(line)
            if channel_sample is None:
                continue
            self._handle_channel_sample(channel_sample)

    def _handle_channel_sample(self, sample: ChannelSample) -> None:
        throttle = self.throttle_aligner.observe_channel_sample(sample)
        if throttle:
            self._latest_throttle = throttle
            self.throttle_view.append(throttle)

        processed = self.preprocessor.process_sample(sample)
        self._handle_preprocessed_sample(processed, sample)

    def _handle_preprocessed_sample(self, processed: PreprocessedSample, sample: ChannelSample) -> None:
        if self._data_recorder:
            self._data_recorder.write_sample(processed)
        fft_channels = self.profile.fft_channel_config.selected_channels()
        if not fft_channels:
            fft_channels = [name for name, role in sample.roles.items() if role in {"vibration", "fft_primary", "fft_optional"}]
        for channel in fft_channels:
            value = processed.ac_channels.get(channel)
            if value is None:
                continue
            self.buffers.append(channel, processed.timestamp, float(value))
            counter = self._sample_counter_by_channel.get(channel, 0) + 1
            self._sample_counter_by_channel[channel] = counter
            if counter % self.fft_analyzer.hop_size == 0:
                buf = self.buffers.get_channel(channel)
                if len(buf) >= self.fft_config.window_size:
                    window = buf.get_recent(self.fft_config.window_size)
                    throttle = self.throttle_aligner.align(float(window.timestamps[len(window.timestamps) // 2]), "nearest")
                    throttle_percent = None if throttle is None else throttle.throttle_percent
                    frame = self.fft_analyzer.analyze(
                        window.values,
                        window.timestamps,
                        throttle_percent=throttle_percent,
                        channel_name=channel,
                    )
                    self._latest_spectrum = frame
                    self._latest_waterfall = self.waterfall_builder.add_frame(frame)
                    if self._data_recorder:
                        self._data_recorder.append_spectrum(frame)
                    self.peak_detector.detect(frame)

        primary = self.profile.fft_channel_config.primary
        self.preprocess_panel.set_dc_estimate(primary, self.preprocessor.get_dc_estimate(primary))

    def _refresh_ui(self) -> None:
        if self._latest_spectrum is not None:
            self.spectrum_view.update_spectrum(self._latest_spectrum)
        if self._latest_waterfall is not None:
            self.waterfall_view.update_matrix(self._latest_waterfall)
        if self._latest_throttle is not None:
            throttle = self._latest_throttle
            self.throttle_percent_label.setText(f"{throttle.throttle_percent:.1f} %")
            self.throttle_raw_label.setText("-" if throttle.raw_value is None else f"{throttle.raw_value:.3f}")
            self.throttle_stale_label.setText("是" if throttle.stale else "否")
            bin_size = self.waterfall_config.throttle_bin_size
            self.throttle_bin_label.setText(str(int(round(throttle.throttle_percent / bin_size))))

    def _update_stats(self, stats: dict) -> None:
        connected = stats.get("connected", False)
        self.stat_connection.setText("已连接" if connected else "未连接")
        self.stat_port.setText(str(stats.get("port", "-")))
        self.stat_byte_rate.setText(f"{stats.get('byte_rate', 0.0):.0f} B/s")
        self.stat_line_rate.setText(f"{stats.get('line_rate', 0.0):.1f} line/s")
        self.stat_sample_rate.setText(f"{stats.get('sample_rate', 0.0):.1f} sample/s")
        self.stat_errors.setText(str(stats.get("parse_errors", 0)))
        self.stat_overflow.setText(str(stats.get("line_overflows", 0)))
        self.stat_buffer.setText(str(stats.get("buffer_length", 0)))
        self.stat_uptime.setText(f"{stats.get('uptime_sec', 0.0):.1f} s")
        self.status.set_stats(f"{stats.get('rx_lines', 0)} lines")

    def _update_preprocess_config(self, config: PreprocessConfig) -> None:
        config.sample_rate = self.fft_panel.sample_rate_spin.value()
        self.preprocess_config = config
        self.preprocessor.update_config(config)
        self.fft_panel.remove_dc_check.setChecked(config.fft_remove_window_mean)
        self.fft_panel.detrend_check.setChecked(config.detrend_enabled)

    def _update_fft_config(self, config: FFTConfig) -> None:
        self.fft_config = config
        self.fft_analyzer = FFTAnalyzer(config)
        self.preprocess_config.sample_rate = config.sample_rate
        self.preprocessor.update_config(self.preprocess_config)
        self.buffers = MultiChannelRingBuffer(max(8192, config.window_size * 8))
        self._reset_analysis_state()

    def _update_waterfall_config(self, *args) -> None:
        self.waterfall_config = WaterfallConfig(
            mode=self.waterfall_mode_combo.currentText(),
            throttle_bin_size=self.bin_spin.value(),
            time_rows=self.waterfall_config.time_rows,
            db_min=self.db_min_spin.value(),
            db_max=self.db_max_spin.value(),
            aggregation=self.aggregation_combo.currentText(),
            ema_alpha=self.waterfall_config.ema_alpha,
            display_freq_min=self.waterfall_config.display_freq_min,
        )
        self.waterfall_view.set_db_range(self.waterfall_config.db_min, self.waterfall_config.db_max)
        self.waterfall_builder.update_config(self.waterfall_config)

    def _open_mapping_editor(
        self,
        focus_prefix: str | None = None,
        latest_line: FireWaterLine | None = None,
    ) -> None:
        if self._mapping_editor is None:
            self._mapping_editor = ChannelMappingEditor(self.mapping_manager, self)
            self._mapping_editor.profile_applied.connect(self._apply_profile)
            self._mapping_editor.finished.connect(lambda: setattr(self, "_mapping_editor", None))
        if focus_prefix is not None:
            self._mapping_editor.focus_prefix(focus_prefix, latest_line)
        self._mapping_editor.show()
        self._mapping_editor.raise_()

    def _open_wizard(self) -> None:
        dialog = ChannelMappingWizard(self.mapping_manager, self)
        if dialog.exec():
            self._apply_profile(self.mapping_manager.profile)

    def _apply_profile(self, profile: ChannelMappingProfile) -> None:
        self.profile = profile
        self.mapping_manager.profile = profile
        self.throttle_aligner.update_config(profile.throttle_config)
        self.profile_label.setText(profile.name)
        self.throttle_channel_label.setText(profile.throttle_config.channel)
        self.fft_channel_label.setText(profile.fft_channel_config.primary)
        messages = self.mapping_manager.validate_profile(profile)
        self.config_status_label.setText("有效" if not any(msg.level == "error" for msg in messages) else "需要配置")
        self._reset_analysis_state()

    def _handle_unknown_prefix(self, line: FireWaterLine) -> None:
        prefix_key = line.prefix
        if prefix_key in self._prompted_unknown_prefixes:
            return
        self._prompted_unknown_prefixes.add(prefix_key)
        label = line.prefix or "无前缀数据"
        box = QMessageBox(self)
        box.setWindowTitle("检测到新的 FireWater prefix")
        box.setText(f"检测到新的 FireWater prefix：{label}\n字段数量：{len(line.values)}\n是否立即配置？")
        configure = box.addButton("立即配置", QMessageBox.ButtonRole.AcceptRole)
        auto_name = box.addButton("自动命名", QMessageBox.ButtonRole.ActionRole)
        temp_ignore = box.addButton("暂时忽略", QMessageBox.ButtonRole.RejectRole)
        permanent_ignore = box.addButton("永久忽略", QMessageBox.ButtonRole.DestructiveRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked == configure:
            self._open_mapping_editor(prefix_key, line)
        elif clicked == auto_name:
            self.mapping_manager.profile.mappings[prefix_key] = PrefixMapping(
                prefix=prefix_key,
                display_name=label,
                fields=[FieldMapping(index=i, name=f"{prefix_key}_ch{i}" if prefix_key else f"ch{i}") for i in range(len(line.values))],
            )
            self._apply_profile(self.mapping_manager.profile)
        elif clicked == permanent_ignore:
            self.mapping_manager.profile.mappings[prefix_key] = PrefixMapping(
                prefix=prefix_key,
                display_name=label,
                fields=[],
                enabled=False,
                ignored=True,
            )
        else:
            self.status.set_warning(f"暂时忽略未知 prefix：{label}")

    def _toggle_raw_logging(self) -> None:
        if self._raw_logger or self._data_recorder:
            self._close_recording()
            return
        directory = QFileDialog.getExistingDirectory(self, "选择 session 文件夹")
        if directory:
            path = Path(directory) / "raw_firewater.log"
            self._raw_logger = RawLogger(path)
            self._data_recorder = DataRecorder(directory)
            self.status.set_file(str(path))
            profile_path = Path(directory) / "channel_mapping_profile.yaml"
            with profile_path.open("w", encoding="utf-8") as file:
                yaml.safe_dump(self.profile.to_dict(), file, allow_unicode=True, sort_keys=False)
            if self._data_recorder:
                self._data_recorder.save_yaml("session_config.yaml", self.config)

    def _log_raw_bytes(self, data: bytes) -> None:
        if self._raw_logger:
            self._raw_logger.write_bytes(data)

    def _warn(self, message: str) -> None:
        self.status.set_warning(message)

    def _close_recording(self) -> None:
        if self._raw_logger:
            self._raw_logger.close()
            self._raw_logger = None
        if self._data_recorder:
            if self._latest_waterfall is not None:
                self._data_recorder.save_waterfall_npz(self._latest_waterfall)
            self._data_recorder.save_spectrum_npz(
                {
                    "dc_removal_mode": self.preprocess_config.dc_mode,
                    "remove_dc": self.fft_config.remove_dc,
                    "ignore_below_hz": self.fft_config.ignore_below_hz,
                }
            )
            self._data_recorder.close()
            self._data_recorder = None
        self.status.set_file("未保存")

    def _load_profile_from_config(self, config: dict) -> ChannelMappingProfile:
        mapping_cfg = config.get("channel_mapping", {})
        active = mapping_cfg.get("active_profile", "default_imu")
        profile_data = mapping_cfg.get("profiles", {}).get(active, {})
        return ChannelMappingProfile.from_dict(active, profile_data)

    def _fft_config_from_yaml(self) -> FFTConfig:
        fft = self.config.get("fft", {})
        acq = self.config.get("acquisition", {})
        return FFTConfig(
            sample_rate=float(acq.get("sample_rate", 1000)),
            window_size=int(fft.get("window_size", 1024)),
            overlap=float(fft.get("overlap", 0.5)),
            window=str(fft.get("window", "hann")),
            remove_dc=bool(fft.get("remove_dc", True)),
            detrend=bool(fft.get("detrend", False)),
            freq_min=float(fft.get("freq_min", 0)),
            freq_max=float(fft.get("freq_max", 500)),
            ignore_below_hz=float(fft.get("ignore_below_hz", 2)),
            db_floor=float(fft.get("db_floor", -120)),
        )

    def _waterfall_config_from_yaml(self) -> WaterfallConfig:
        cfg = self.config.get("waterfall", {})
        return WaterfallConfig(
            mode=str(cfg.get("mode", "throttle")),
            throttle_bin_size=float(cfg.get("throttle_bin_size", 2)),
            time_rows=int(cfg.get("time_rows", 300)),
            db_min=float(cfg.get("db_min", -90)),
            db_max=float(cfg.get("db_max", -20)),
            aggregation=str(cfg.get("aggregation", "ema")),
            ema_alpha=float(cfg.get("ema_alpha", 0.2)),
            min_count_per_bin=int(cfg.get("min_count_per_bin", 3)),
            display_freq_min=float(cfg.get("display_freq_min", 2)),
        )

    def _peak_config_from_yaml(self):
        from processing.peak_detector import PeakConfig

        cfg = self.config.get("peak", {})
        return PeakConfig(
            enabled=bool(cfg.get("enabled", True)),
            ignore_below_hz=float(cfg.get("ignore_below_hz", 5)),
            top_n=int(cfg.get("top_n", 5)),
            min_prominence_db=float(cfg.get("min_prominence_db", 6)),
        )

    def _apply_config_to_widgets(self) -> None:
        self.acquisition_panel.sample_rate_spin.setValue(self.fft_config.sample_rate)
        self.fft_panel.sample_rate_spin.setValue(self.fft_config.sample_rate)
        self.fft_panel.window_size_combo.setCurrentText(str(self.fft_config.window_size))
        self.fft_panel.overlap_combo.setCurrentText(str(self.fft_config.overlap))
        self.fft_panel.window_combo.setCurrentText(self.fft_config.window)
        self.fft_panel.freq_min_spin.setValue(self.fft_config.freq_min)
        self.fft_panel.freq_max_spin.setValue(float(self.fft_config.freq_max or 500))
        self.fft_panel.ignore_spin.setValue(self.fft_config.ignore_below_hz)
        self.fft_panel.remove_dc_check.setChecked(self.fft_config.remove_dc)
        self.fft_panel.detrend_check.setChecked(self.fft_config.detrend)

        self.preprocess_panel.enable_check.setChecked(self.preprocess_config.dc_enabled)
        self.preprocess_panel.mode_combo.setCurrentText(self.preprocess_config.dc_mode)
        self.preprocess_panel.ema_spin.setValue(self.preprocess_config.ema_alpha)
        self.preprocess_panel.running_spin.setValue(self.preprocess_config.running_mean_window_sec)
        self.preprocess_panel.highpass_spin.setValue(self.preprocess_config.highpass_cutoff_hz)
        self.preprocess_panel.order_spin.setValue(self.preprocess_config.highpass_order)
        self.preprocess_panel.window_mean_check.setChecked(self.preprocess_config.fft_remove_window_mean)
        self.preprocess_panel.detrend_check.setChecked(self.preprocess_config.detrend_enabled)
