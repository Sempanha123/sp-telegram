from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QAbstractItemView

from app.dialogs.device_management_dialog import DeviceManagementDialog


@dataclass
class _Device:
    device_id: str = "device-1"
    device_name: str = "Desktop"
    platform: str = "Windows"
    is_current: bool = True
    last_seen_at: str = "2026-09-02"
    is_active: bool = True


def test_device_management_dialog_constructs_and_configures_table(qapp) -> None:
    dialog = DeviceManagementDialog([_Device()])
    try:
        assert dialog.tbl_license_devices.rowCount() == 1
        assert (
            dialog.tbl_license_devices.selectionBehavior()
            == QAbstractItemView.SelectionBehavior.SelectRows
        )
        assert dialog.tbl_license_devices.item(0, 0).text() == "Desktop"
    finally:
        dialog.deleteLater()
        qapp.processEvents()
