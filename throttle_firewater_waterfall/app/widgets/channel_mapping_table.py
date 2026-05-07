from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHeaderView,
    QLineEdit,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
)

from models.channel_mapping import CHANNEL_ROLES, OUT_OF_RANGE_POLICIES, FieldMapping


class ChannelMappingTable(QTableWidget):
    mapping_changed = Signal()

    HEADERS = [
        "启用",
        "字段序号",
        "当前原始值",
        "通道名称",
        "通道角色",
        "单位",
        "scale",
        "offset",
        "小数位",
        "最小合理值",
        "最大合理值",
        "超范围处理",
        "备注",
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(0, len(self.HEADERS), parent)
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setStretchLastSection(True)
        self._raw_values: list[float] = []

    def set_fields(self, fields: list[FieldMapping], raw_values: list[float] | None = None) -> None:
        self.blockSignals(True)
        self.setRowCount(0)
        self._raw_values = list(raw_values or [])
        for field in sorted(fields, key=lambda item: item.index):
            self._append_field_row(field)
        self.blockSignals(False)

    def set_raw_values(self, raw_values: list[float]) -> None:
        self._raw_values = list(raw_values)
        for row in range(self.rowCount()):
            index_item = self.item(row, 1)
            if not index_item:
                continue
            index = int(index_item.text())
            text = "" if index >= len(raw_values) else f"{raw_values[index]:.6g}"
            self.setItem(row, 2, QTableWidgetItem(text))

    def fields(self) -> list[FieldMapping]:
        result: list[FieldMapping] = []
        for row in range(self.rowCount()):
            enabled = self.cellWidget(row, 0).isChecked()  # type: ignore[union-attr]
            index = int(self.item(row, 1).text())
            name = self.cellWidget(row, 3).text().strip()  # type: ignore[union-attr]
            role = self.cellWidget(row, 4).currentText()  # type: ignore[union-attr]
            unit = self.cellWidget(row, 5).text().strip()  # type: ignore[union-attr]
            scale = self.cellWidget(row, 6).value()  # type: ignore[union-attr]
            offset = self.cellWidget(row, 7).value()  # type: ignore[union-attr]
            decimals = self.cellWidget(row, 8).value()  # type: ignore[union-attr]
            min_value = self._optional_spin_value(row, 9)
            max_value = self._optional_spin_value(row, 10)
            policy = self.cellWidget(row, 11).currentText()  # type: ignore[union-attr]
            note = self.cellWidget(row, 12).text()  # type: ignore[union-attr]
            result.append(
                FieldMapping(
                    index=index,
                    name=name,
                    role=role,
                    unit=unit,
                    enabled=enabled,
                    scale=scale,
                    offset=offset,
                    decimals=decimals,
                    min_value=min_value,
                    max_value=max_value,
                    out_of_range_policy=policy,
                    note=note,
                )
            )
        return result

    def ensure_field_count(self, count: int, prefix: str = "") -> bool:
        existing = {int(self.item(row, 1).text()) for row in range(self.rowCount()) if self.item(row, 1)}
        changed = False
        for index in range(count):
            if index not in existing:
                self._append_field_row(FieldMapping(index=index, name=self._auto_name(prefix, index)))
                changed = True
        if changed:
            self.mapping_changed.emit()
        return changed

    def apply_throttle_gz_preset(self) -> None:
        """Configure field 0 as throttle and field 1 as gz."""

        self.ensure_field_count(2)
        self._set_row_values(0, name="throttle", role="throttle", unit="%", min_value=0.0, max_value=100.0, policy="clamp")
        self._set_row_values(1, name="gz", role="fft_primary", unit="dps", min_value=-2000.0, max_value=2000.0, policy="warn")
        self.mapping_changed.emit()

    def _append_field_row(self, field: FieldMapping) -> None:
        row = self.rowCount()
        self.insertRow(row)

        enabled = QCheckBox()
        enabled.setChecked(field.enabled)
        enabled.toggled.connect(self.mapping_changed)
        self.setCellWidget(row, 0, enabled)

        self.setItem(row, 1, QTableWidgetItem(str(field.index)))
        raw = "" if field.index >= len(self._raw_values) else f"{self._raw_values[field.index]:.6g}"
        self.setItem(row, 2, QTableWidgetItem(raw))

        name = QLineEdit(field.name)
        name.textChanged.connect(self.mapping_changed)
        self.setCellWidget(row, 3, name)

        role = QComboBox()
        role.addItems(list(CHANNEL_ROLES))
        role.setCurrentText(field.role if field.role in CHANNEL_ROLES else "custom")
        role.currentTextChanged.connect(self.mapping_changed)
        self.setCellWidget(row, 4, role)

        unit = QLineEdit(field.unit)
        unit.textChanged.connect(self.mapping_changed)
        self.setCellWidget(row, 5, unit)

        scale = QDoubleSpinBox()
        scale.setDecimals(8)
        scale.setRange(-1e9, 1e9)
        scale.setValue(field.scale)
        scale.valueChanged.connect(self.mapping_changed)
        self.setCellWidget(row, 6, scale)

        offset = QDoubleSpinBox()
        offset.setDecimals(8)
        offset.setRange(-1e9, 1e9)
        offset.setValue(field.offset)
        offset.valueChanged.connect(self.mapping_changed)
        self.setCellWidget(row, 7, offset)

        decimals = QSpinBox()
        decimals.setRange(0, 12)
        decimals.setValue(field.decimals)
        decimals.valueChanged.connect(self.mapping_changed)
        self.setCellWidget(row, 8, decimals)

        self.setCellWidget(row, 9, self._range_spin(field.min_value))
        self.setCellWidget(row, 10, self._range_spin(field.max_value))

        policy = QComboBox()
        policy.addItems(list(OUT_OF_RANGE_POLICIES))
        policy.setCurrentText(field.out_of_range_policy)
        policy.currentTextChanged.connect(self.mapping_changed)
        self.setCellWidget(row, 11, policy)

        note = QLineEdit(field.note)
        note.textChanged.connect(self.mapping_changed)
        self.setCellWidget(row, 12, note)

    def _set_row_values(
        self,
        row: int,
        *,
        name: str,
        role: str,
        unit: str,
        min_value: float | None,
        max_value: float | None,
        policy: str,
    ) -> None:
        widgets = {
            "name": self.cellWidget(row, 3),
            "role": self.cellWidget(row, 4),
            "unit": self.cellWidget(row, 5),
            "min": self.cellWidget(row, 9),
            "max": self.cellWidget(row, 10),
            "policy": self.cellWidget(row, 11),
        }
        if widgets["name"] is not None:
            widgets["name"].setText(name)  # type: ignore[union-attr]
        if widgets["role"] is not None:
            widgets["role"].setCurrentText(role)  # type: ignore[union-attr]
        if widgets["unit"] is not None:
            widgets["unit"].setText(unit)  # type: ignore[union-attr]
        if widgets["min"] is not None:
            widgets["min"].setValue(-1e12 if min_value is None else min_value)  # type: ignore[union-attr]
        if widgets["max"] is not None:
            widgets["max"].setValue(-1e12 if max_value is None else max_value)  # type: ignore[union-attr]
        if widgets["policy"] is not None:
            widgets["policy"].setCurrentText(policy)  # type: ignore[union-attr]

    def _range_spin(self, value: float | None) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setDecimals(6)
        spin.setRange(-1e12, 1e12)
        spin.setSpecialValueText("None")
        spin.setValue(-1e12 if value is None else value)
        spin.valueChanged.connect(self.mapping_changed)
        return spin

    def _optional_spin_value(self, row: int, column: int) -> float | None:
        widget = self.cellWidget(row, column)
        value = widget.value()  # type: ignore[union-attr]
        if value <= -1e12 + 1:
            return None
        return float(value)

    @staticmethod
    def _auto_name(prefix: str, index: int) -> str:
        return f"{prefix}_ch{index}" if prefix else f"ch{index}"
