from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from core.channel_mapping import ChannelMappingManager
from models.channel_mapping import ChannelMappingProfile, FFTChannelConfig, FieldMapping, PrefixMapping, ThrottleConfig


TEMPLATES = {
    "模板 A：油门 + GZ": [("throttle", "throttle", "%"), ("gz", "fft_primary", "dps")],
    "模板 B：完整 IMU + 油门": [
        ("ax", "imu_acc", "g"),
        ("ay", "imu_acc", "g"),
        ("az", "imu_acc", "g"),
        ("gx", "imu_gyro", "dps"),
        ("gy", "imu_gyro", "dps"),
        ("gz", "fft_primary", "dps"),
        ("throttle", "throttle", "%"),
    ],
    "模板 C：油门 + 三轴陀螺仪": [
        ("throttle", "throttle", "%"),
        ("gx", "imu_gyro", "dps"),
        ("gy", "imu_gyro", "dps"),
        ("gz", "fft_primary", "dps"),
    ],
    "模板 D：油门 + 多路振动": [
        ("throttle", "throttle", "%"),
        ("vib0", "fft_primary", "g"),
        ("vib1", "vibration", "g"),
        ("vib2", "vibration", "g"),
        ("vib3", "vibration", "g"),
    ],
    "模板 E：自定义": [],
}


class ChannelMappingWizard(QDialog):
    def __init__(self, manager: ChannelMappingManager, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("快速配置向导")
        self.manager = manager
        self.template_combo = QComboBox()
        self.template_combo.addItems(list(TEMPLATES.keys()))
        self.prefix_edit = QLineEdit("imu")
        self.field_count_spin = QSpinBox()
        self.field_count_spin.setRange(1, 128)
        self.field_count_spin.setValue(7)
        self.sample_rate_edit = QLineEdit("1000")
        self.info_label = QLabel("第 1 步：连接串口或开启模拟数据。\n第 2 步：选择模板并保存配置。")
        self.info_label.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        form = QFormLayout()
        form.addRow("模板", self.template_combo)
        form.addRow("prefix", self.prefix_edit)
        form.addRow("字段数量", self.field_count_spin)
        form.addRow("采样率", self.sample_rate_edit)
        layout = QVBoxLayout(self)
        layout.addWidget(self.info_label)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self.template_combo.currentTextChanged.connect(self._template_changed)
        self._template_changed(self.template_combo.currentText())

    def profile(self) -> ChannelMappingProfile:
        template = TEMPLATES[self.template_combo.currentText()]
        field_count = self.field_count_spin.value()
        fields: list[FieldMapping] = []
        for index in range(field_count):
            if index < len(template):
                name, role, unit = template[index]
            else:
                name, role, unit = f"ch{index}", "normal", ""
            fields.append(FieldMapping(index=index, name=name, role=role, unit=unit))
        prefix = self.prefix_edit.text().strip()
        throttle_name = next((field.name for field in fields if field.role == "throttle"), "throttle")
        fft_primary = next((field.name for field in fields if field.role == "fft_primary"), "")
        fft_optional = [field.name for field in fields if field.role in {"vibration", "fft_optional", "imu_gyro", "imu_acc"}]
        return ChannelMappingProfile(
            name="wizard_profile",
            description="由快速配置向导生成",
            mappings={
                prefix: PrefixMapping(
                    prefix=prefix,
                    display_name=prefix or "无前缀数据",
                    fields=fields,
                )
            },
            throttle_config=ThrottleConfig(channel=throttle_name),
            fft_channel_config=FFTChannelConfig(primary=fft_primary, optional=fft_optional),
        )

    def accept(self) -> None:
        self.manager.profile = self.profile()
        super().accept()

    def _template_changed(self, name: str) -> None:
        self.field_count_spin.setValue(max(1, len(TEMPLATES[name]) or self.field_count_spin.value()))
