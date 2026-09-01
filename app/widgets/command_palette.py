from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout

from app.constants import NAV_ITEMS
from app.icons import IconManager


class CommandPaletteDialog(QDialog):
    """Ctrl+K command palette: search pages and quick actions, then jump.

    Pages come from NAV_ITEMS so the palette always matches the real navigation
    surface. Quick actions are lightweight shortcuts wired by MainWindow.
    """

    pageSelected = Signal(str)
    actionSelected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Command Palette")
        self.setModal(True)
        self.resize(520, 420)
        root = QVBoxLayout(self); root.setContentsMargins(14, 14, 14, 14); root.setSpacing(10)
        self.le_query = QLineEdit(); self.le_query.setObjectName("le_command_palette"); self.le_query.setPlaceholderText("Type to search pages and actions…"); self.le_query.setClearButtonEnabled(True)
        root.addWidget(self.le_query)
        self.list_results = QListWidget(); self.list_results.setObjectName("list_command_palette")
        root.addWidget(self.list_results, 1)
        self.lbl_hint = QLabel("↑↓ to navigate · Enter to open · Esc to close"); self.lbl_hint.setProperty("muted", True)
        root.addWidget(self.lbl_hint)
        self._entries: list[tuple[str, str, str]] = []
        self.le_query.textChanged.connect(self._filter)
        self.list_results.itemActivated.connect(self._activate)
        self._build_entries()
        self._filter("")
        self.le_query.setFocus()

    def _build_entries(self) -> None:
        for key, title, _obj in NAV_ITEMS:
            self._entries.append((title, "page", key))
        for label, action in [
            ("Toggle Theme", "toggle_theme"),
            ("Pause / Resume Operations", "toggle_pause"),
            ("Create Campaign", "create_campaign"),
            ("Add Account", "add_account"),
            ("Add Group", "add_group"),
            ("Run Diagnostics", "run_diagnostics"),
            ("Security Audit", "security_audit"),
            ("Backup Database", "backup"),
        ]:
            self._entries.append((label, "action", action))

    def _filter(self, text: str) -> None:
        query = str(text).strip().lower()
        self.list_results.clear()
        for label, kind, key in self._entries:
            if not query or query in label.lower() or query in key.lower():
                item = QListWidgetItem(label)
                item.setIcon(IconManager.get(key) if kind == "page" else IconManager.get("check"))
                item.setData(Qt.ItemDataRole.UserRole, (kind, key))
                self.list_results.addItem(item)
        if self.list_results.count():
            self.list_results.setCurrentRow(0)

    def _activate(self, item: QListWidgetItem) -> None:
        kind, key = item.data(Qt.ItemDataRole.UserRole)
        if kind == "page":
            self.pageSelected.emit(key)
        else:
            self.actionSelected.emit(key)
        self.accept()