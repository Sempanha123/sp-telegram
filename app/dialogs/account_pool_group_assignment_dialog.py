from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QListWidget, QListWidgetItem, QVBoxLayout
from app.dialogs.dialog_compat import *


class AccountPoolGroupAssignmentDialog(QDialog):
    """Choose saved groups for one local account mapping refresh/add operation."""

    def __init__(self, account_name: str, groups: list[object], mapped_group_ids: set[int] | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("dialog_account_pool_assign_groups")
        self.setWindowTitle("Assign Groups - SP Telegram")
        self.resize(520, 520)
        mapped_group_ids = set(mapped_group_ids or set())
        root = QVBoxLayout(self)
        title = QLabel(f"Assign saved groups to {account_name}")
        title.setProperty("dialogTitle", True)
        root.addWidget(title)
        help_text = QLabel(
            "Checked groups will be verified through the existing Telegram permission service. "
            "This stores legitimate account↔group mappings; it does not start a Telegram job."
        )
        help_text.setWordWrap(True); help_text.setProperty("muted", True); root.addWidget(help_text)
        self.list_groups = QListWidget(); self.list_groups.setObjectName("lst_account_pool_groups")
        for group in groups:
            gid = int(getattr(group, "id", 0) or 0)
            if not gid:
                continue
            title_text = getattr(group, "title", None) or f"Group {gid}"
            username = getattr(group, "username", None)
            suffix = f"  @{username}" if username else ""
            item = QListWidgetItem(f"{title_text}{suffix}")
            item.setData(Qt.ItemDataRole.UserRole, gid)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if gid in mapped_group_ids else Qt.CheckState.Unchecked)
            self.list_groups.addItem(item)
        root.addWidget(self.list_groups, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)

    def selected_group_ids(self) -> list[int]:
        result = []
        for i in range(self.list_groups.count()):
            item = self.list_groups.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                result.append(int(item.data(Qt.ItemDataRole.UserRole)))
        return result

# Add compatibility attributes for older PySide6 versions
if not hasattr(AccountPoolGroupAssignmentDialog, 'Accepted'):
    AccountPoolGroupAssignmentDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(AccountPoolGroupAssignmentDialog, 'Rejected'):
    AccountPoolGroupAssignmentDialog.Rejected = QDialog.DialogCode.Rejected
