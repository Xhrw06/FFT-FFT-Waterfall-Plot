from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.widgets.channel_mapping_table import ChannelMappingTable
from core.channel_mapping import ChannelMappingManager
from models.channel_mapping import (
    FFTChannelConfig,
    FieldMapping,
    PrefixMapping,
    ThrottleConfig,
)
from models.firewater import FireWaterLine


NO_PREFIX_LABEL = "No prefix data"


class ChannelMappingEditor(QDialog):
    """GUI editor for FireWater prefix and field mappings.

    This widget is intentionally tolerant of live data changes. If a prefix was
    created with one field but the incoming FireWater line has two or more
    fields, the table expands immediately instead of requiring the user to close
    and reopen the dialog.
    """

    profile_applied = Signal(object)

    def __init__(self, manager: ChannelMappingManager, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("FireWater Channel Mapping")
        self.resize(1120, 760)
        self.manager = manager
        self.profile = manager.profile
        self._current_prefix = next(iter(self.profile.mappings.keys()), "")
        self._latest_lines: dict[str, FireWaterLine] = {}
        self._loading = False

        self.prefix_list = QListWidget()
        self.add_prefix_button = QPushButton("New prefix")
        self.delete_prefix_button = QPushButton("Delete prefix")
        self.enabled_check = QCheckBox("Enable prefix")
        self.enabled_check.setChecked(True)
        self.ignore_check = QCheckBox("Ignore prefix")
        self.display_name_edit = QLineEdit()
        self.unknown_policy_combo = QComboBox()
        self.unknown_policy_combo.addItems(["auto_name", "ignore"])
        self.missing_policy_combo = QComboBox()
        self.missing_policy_combo.addItems(["fill_none", "ignore"])

        self.raw_line_label = QLabel("-")
        self.raw_line_label.setWordWrap(True)
        self.parse_label = QLabel("-")
        self.table = ChannelMappingTable()
        self.throttle_gz_preset_button = QPushButton("Preset: field0 throttle, field1 gz")

        self.throttle_channel_edit = QLineEdit(self.profile.throttle_config.channel)
        self.throttle_unit_edit = QLineEdit(self.profile.throttle_config.unit)
        self.throttle_normalize_check = QCheckBox("Normalize to output range")
        self.throttle_normalize_check.setChecked(self.profile.throttle_config.normalize)
        self.throttle_input_min = QLineEdit(str(self.profile.throttle_config.input_min))
        self.throttle_input_max = QLineEdit(str(self.profile.throttle_config.input_max))
        self.throttle_output_min = QLineEdit(str(self.profile.throttle_config.output_min))
        self.throttle_output_max = QLineEdit(str(self.profile.throttle_config.output_max))
        self.throttle_reverse_check = QCheckBox("Reverse")
        self.throttle_reverse_check.setChecked(self.profile.throttle_config.reverse)
        self.throttle_deadband = QLineEdit(str(self.profile.throttle_config.deadband))
        self.throttle_alpha = QLineEdit(str(self.profile.throttle_config.smoothing_alpha))
        self.throttle_timeout = QLineEdit(str(self.profile.throttle_config.timeout_sec))

        self.fft_primary_combo = QComboBox()
        self.fft_optional_edit = QLineEdit(",".join(self.profile.fft_channel_config.optional))

        self.apply_button = QPushButton("Apply")
        self.save_button = QPushButton("Save")
        self.load_button = QPushButton("Load")
        self.export_button = QPushButton("Export")
        self.import_button = QPushButton("Import")
        self.close_button = QPushButton("Close")

        self._build_layout()
        self._connect()
        self._reload_prefix_list()
        self._load_current_prefix()

    def observe_line(self, line: FireWaterLine) -> None:
        """Update preview and expand field rows for the incoming line."""

        if not line.valid or line.is_image_packet:
            return
        self._latest_lines[line.prefix] = line
        self.manager.last_raw_by_prefix[line.prefix] = line
        self.manager.observed_prefix_counts[line.prefix] = max(
            1,
            self.manager.observed_prefix_counts.get(line.prefix, 0),
        )

        if line.prefix not in self.profile.mappings:
            self._reload_prefix_list()

        if line.prefix == self._current_prefix:
            self._show_line_preview(line)
            self.table.ensure_field_count(len(line.values), self._current_prefix)
            self.table.set_raw_values(line.values)
            self._sync_current_prefix()

    def focus_prefix(self, prefix: str, latest_line: FireWaterLine | None = None) -> None:
        """Select a prefix, optionally seeding the editor with a fresh line."""

        if latest_line is not None:
            self.observe_line(latest_line)
        self._current_prefix = prefix
        self._reload_prefix_list()
        self._load_current_prefix()

    def _build_layout(self) -> None:
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("prefix"))
        left_layout.addWidget(self.prefix_list)
        left_layout.addWidget(self.add_prefix_button)
        left_layout.addWidget(self.delete_prefix_button)

        prefix_group = QGroupBox("Prefix")
        prefix_form = QFormLayout(prefix_group)
        prefix_form.addRow("", self.enabled_check)
        prefix_form.addRow("", self.ignore_check)
        prefix_form.addRow("Display name", self.display_name_edit)
        prefix_form.addRow("Unknown fields", self.unknown_policy_combo)
        prefix_form.addRow("Missing fields", self.missing_policy_combo)

        preview_group = QGroupBox("Live Raw Preview")
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.addWidget(QLabel("Latest line:"))
        preview_layout.addWidget(self.raw_line_label)
        preview_layout.addWidget(QLabel("Parse result:"))
        preview_layout.addWidget(self.parse_label)
        preview_layout.addWidget(self.throttle_gz_preset_button)

        throttle_group = QGroupBox("Throttle")
        throttle_form = QFormLayout(throttle_group)
        throttle_form.addRow("Channel", self.throttle_channel_edit)
        throttle_form.addRow("Unit", self.throttle_unit_edit)
        throttle_form.addRow("", self.throttle_normalize_check)
        throttle_form.addRow("Input min", self.throttle_input_min)
        throttle_form.addRow("Input max", self.throttle_input_max)
        throttle_form.addRow("Output min", self.throttle_output_min)
        throttle_form.addRow("Output max", self.throttle_output_max)
        throttle_form.addRow("", self.throttle_reverse_check)
        throttle_form.addRow("Deadband", self.throttle_deadband)
        throttle_form.addRow("Smoothing alpha", self.throttle_alpha)
        throttle_form.addRow("Timeout sec", self.throttle_timeout)

        fft_group = QGroupBox("FFT Channels")
        fft_form = QFormLayout(fft_group)
        fft_form.addRow("Primary", self.fft_primary_combo)
        fft_form.addRow("Optional", self.fft_optional_edit)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(prefix_group)
        right_layout.addWidget(preview_group)
        right_layout.addWidget(self.table, 1)
        right_layout.addWidget(throttle_group)
        right_layout.addWidget(fft_group)

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([240, 880])

        bottom = QHBoxLayout()
        bottom.addWidget(self.import_button)
        bottom.addWidget(self.export_button)
        bottom.addStretch(1)
        bottom.addWidget(self.load_button)
        bottom.addWidget(self.save_button)
        bottom.addWidget(self.apply_button)
        bottom.addWidget(self.close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(splitter, 1)
        layout.addLayout(bottom)

    def _connect(self) -> None:
        self.prefix_list.currentTextChanged.connect(self._select_prefix_label)
        self.add_prefix_button.clicked.connect(self._add_prefix)
        self.delete_prefix_button.clicked.connect(self._delete_prefix)
        self.table.mapping_changed.connect(self._sync_current_prefix)
        self.enabled_check.toggled.connect(self._sync_current_prefix)
        self.ignore_check.toggled.connect(self._sync_current_prefix)
        self.display_name_edit.textChanged.connect(self._sync_current_prefix)
        self.unknown_policy_combo.currentTextChanged.connect(self._sync_current_prefix)
        self.missing_policy_combo.currentTextChanged.connect(self._sync_current_prefix)
        self.apply_button.clicked.connect(self._apply)
        self.close_button.clicked.connect(self.close)
        self.save_button.clicked.connect(self._save_profile)
        self.load_button.clicked.connect(self._load_profile)
        self.export_button.clicked.connect(self._save_profile)
        self.import_button.clicked.connect(self._load_profile)
        self.throttle_gz_preset_button.clicked.connect(self._apply_throttle_gz_preset)

    def _reload_prefix_list(self) -> None:
        current = self._current_prefix
        prefixes = self.manager.get_known_prefixes()
        if current and current not in prefixes:
            prefixes.append(current)
        labels = [self._prefix_label(prefix) for prefix in prefixes]

        self.prefix_list.blockSignals(True)
        self.prefix_list.clear()
        self.prefix_list.addItems(labels)
        if labels:
            label = self._prefix_label(current)
            self.prefix_list.setCurrentRow(labels.index(label) if label in labels else 0)
        self.prefix_list.blockSignals(False)

    def _select_prefix_label(self, label: str) -> None:
        if not label:
            return
        self._sync_current_prefix()
        self._current_prefix = "" if label == NO_PREFIX_LABEL else label
        self._load_current_prefix()

    def _load_current_prefix(self) -> None:
        self._loading = True
        latest = self._latest_lines.get(self._current_prefix) or self.manager.last_raw_by_prefix.get(self._current_prefix)
        mapping = self.profile.mappings.get(self._current_prefix)
        if mapping is None:
            field_count = len(latest.values) if latest else 2
            mapping = PrefixMapping(
                prefix=self._current_prefix,
                display_name=self._prefix_label(self._current_prefix),
                fields=[FieldMapping(i, self._auto_name(self._current_prefix, i)) for i in range(field_count)],
                unknown_field_policy="auto_name",
                missing_field_policy="fill_none",
                enabled=True,
            )
            self.profile.mappings[self._current_prefix] = mapping

        self.enabled_check.setChecked(mapping.enabled)
        self.ignore_check.setChecked(mapping.ignored)
        self.display_name_edit.setText(mapping.display_name or self._prefix_label(mapping.prefix))
        self.unknown_policy_combo.setCurrentText(mapping.unknown_field_policy)
        self.missing_policy_combo.setCurrentText(mapping.missing_field_policy)
        self.table.set_fields(mapping.fields, latest.values if latest else [])

        if latest:
            self.table.ensure_field_count(len(latest.values), self._current_prefix)
            self.table.set_raw_values(latest.values)
            self._show_line_preview(latest)
        else:
            self.raw_line_label.setText("-")
            self.parse_label.setText("Waiting for data")

        self._loading = False
        self._sync_current_prefix()

    def _sync_current_prefix(self, *args) -> None:
        if not hasattr(self, "table") or self._loading:
            return
        mapping = PrefixMapping(
            prefix=self._current_prefix,
            display_name=self.display_name_edit.text() or self._prefix_label(self._current_prefix),
            fields=self.table.fields(),
            unknown_field_policy=self.unknown_policy_combo.currentText(),
            missing_field_policy=self.missing_policy_combo.currentText(),
            enabled=self.enabled_check.isChecked(),
            ignored=self.ignore_check.isChecked(),
        )
        self.profile.mappings[self._current_prefix] = mapping
        self._refresh_fft_combo()

    def _refresh_fft_combo(self) -> None:
        channels = []
        for mapping in self.profile.mappings.values():
            for field in mapping.fields:
                if field.enabled and field.role in {"vibration", "fft_primary", "fft_optional", "imu_acc", "imu_gyro"}:
                    channels.append(field.name)
        current = self.profile.fft_channel_config.primary or self.fft_primary_combo.currentText()
        self.fft_primary_combo.blockSignals(True)
        self.fft_primary_combo.clear()
        self.fft_primary_combo.addItems(sorted(dict.fromkeys(channels)))
        if current:
            idx = self.fft_primary_combo.findText(current)
            if idx >= 0:
                self.fft_primary_combo.setCurrentIndex(idx)
        self.fft_primary_combo.blockSignals(False)

    def _add_prefix(self) -> None:
        base = "custom"
        index = 1
        prefix = base
        while prefix in self.profile.mappings:
            index += 1
            prefix = f"{base}_{index}"
        self.profile.mappings[prefix] = PrefixMapping(
            prefix=prefix,
            display_name=prefix,
            fields=[FieldMapping(0, f"{prefix}_ch0"), FieldMapping(1, f"{prefix}_ch1")],
        )
        self._current_prefix = prefix
        self._reload_prefix_list()
        self._load_current_prefix()

    def _delete_prefix(self) -> None:
        if self._current_prefix in self.profile.mappings:
            del self.profile.mappings[self._current_prefix]
            self._current_prefix = next(iter(self.profile.mappings.keys()), "")
            self._reload_prefix_list()
            self._load_current_prefix()

    def _apply(self) -> None:
        self._sync_current_prefix()
        try:
            self.profile.throttle_config = self._throttle_config()
        except ValueError as exc:
            QMessageBox.warning(self, "Throttle config error", str(exc))
            return
        self.profile.fft_channel_config = FFTChannelConfig(
            primary=self.fft_primary_combo.currentText(),
            optional=[item.strip() for item in self.fft_optional_edit.text().split(",") if item.strip()],
        )
        messages = self.manager.validate_profile(self.profile)
        errors = [msg.message for msg in messages if msg.level == "error"]
        if errors:
            QMessageBox.warning(self, "Invalid mapping", "\n".join(errors))
            return
        self.manager.profile = self.profile
        self.profile_applied.emit(self.profile)
        QMessageBox.information(self, "Applied", "Channel mapping is applied to subsequent data.")

    def _apply_throttle_gz_preset(self) -> None:
        self.table.apply_throttle_gz_preset()
        self.throttle_channel_edit.setText("throttle")
        self.throttle_unit_edit.setText("%")
        self.throttle_normalize_check.setChecked(True)
        self.throttle_input_min.setText("0")
        self.throttle_input_max.setText("100")
        self.throttle_output_min.setText("0")
        self.throttle_output_max.setText("100")
        self.throttle_reverse_check.setChecked(False)
        self.fft_optional_edit.setText("")
        self._sync_current_prefix()
        idx = self.fft_primary_combo.findText("gz")
        if idx >= 0:
            self.fft_primary_combo.setCurrentIndex(idx)

    def _save_profile(self) -> None:
        self._apply_without_dialog()
        path, _ = QFileDialog.getSaveFileName(self, "Save channel mapping", "channel_mapping_profile.yaml", "YAML (*.yaml *.yml)")
        if path:
            self.manager.save_profile(path)

    def _load_profile(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load channel mapping", "", "YAML (*.yaml *.yml)")
        if path:
            self.profile = self.manager.load_profile(path)
            self._current_prefix = next(iter(self.profile.mappings.keys()), "")
            self._reload_prefix_list()
            self._load_current_prefix()
            self.profile_applied.emit(self.profile)

    def _apply_without_dialog(self) -> None:
        self._sync_current_prefix()
        self.profile.throttle_config = self._throttle_config()
        self.profile.fft_channel_config = FFTChannelConfig(
            primary=self.fft_primary_combo.currentText(),
            optional=[item.strip() for item in self.fft_optional_edit.text().split(",") if item.strip()],
        )
        self.manager.profile = self.profile

    def _throttle_config(self) -> ThrottleConfig:
        return ThrottleConfig(
            channel=self.throttle_channel_edit.text().strip() or "throttle",
            unit=self.throttle_unit_edit.text().strip() or "%",
            normalize=self.throttle_normalize_check.isChecked(),
            input_min=float(self.throttle_input_min.text()),
            input_max=float(self.throttle_input_max.text()),
            output_min=float(self.throttle_output_min.text()),
            output_max=float(self.throttle_output_max.text()),
            reverse=self.throttle_reverse_check.isChecked(),
            deadband=float(self.throttle_deadband.text()),
            smoothing_alpha=float(self.throttle_alpha.text()),
            timeout_sec=float(self.throttle_timeout.text()),
        )

    def _show_line_preview(self, line: FireWaterLine) -> None:
        self.raw_line_label.setText(line.raw_line)
        values = ", ".join(f"{i}={value:.6g}" for i, value in enumerate(line.values))
        self.parse_label.setText(
            f"prefix: {self._prefix_label(line.prefix)} | fields: {len(line.values)} | "
            f"table rows: {self.table.rowCount()} | {values}"
        )

    @staticmethod
    def _prefix_label(prefix: str) -> str:
        return prefix or NO_PREFIX_LABEL

    @staticmethod
    def _auto_name(prefix: str, index: int) -> str:
        return f"{prefix}_ch{index}" if prefix else f"ch{index}"
