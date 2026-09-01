from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from app.constants import NAV_ITEMS
from app.icons import IconManager
from app.styles.tokens import SIDEBAR_COLLAPSED, SIDEBAR_EXPANDED


class Sidebar(QFrame):
    pageRequested = Signal(str, str)
    collapsedChanged = Signal(bool)

    ORDER = [
        "dashboard",
        "accounts", "account_pool", "account_health",
        "groups",
        "members", "collector", "blacklist",
        "campaigns", "scheduler", "templates",
        "operations", "jobs", "analytics", "alerts", "logs",
        "license", "settings",
    ]
    SECTIONS = {
        "accounts": "MANAGEMENT",
        "campaigns": "CONTENT",
        "operations": "OPERATIONS",
        "license": "SYSTEM",
    }
    # Pages removed from sidebar but still navigable from dashboard cards / cross-page links:
    # "source_groups", "target_groups" → accessible from Groups page filters
    # "sessions" → accessible from Accounts page
    # "restrictions" → accessible from Health Center
    ICONS = {
        "dashboard": "dashboard", "operations": "operations", "accounts": "accounts", "account_pool": "accounts",
        "account_health": "health", "restrictions": "restrictions", "sessions": "sessions",
        "groups": "groups", "source_groups": "source_groups", "target_groups": "target_groups",
        "members": "members", "collector": "collector", "blacklist": "blacklist",
        "campaigns": "campaigns", "scheduler": "scheduler", "templates": "templates",
        "jobs": "jobs", "analytics": "analytics", "alerts": "alerts", "logs": "logs", "license": "license", "settings": "settings",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.expanded_width = SIDEBAR_EXPANDED
        self.compact_width = SIDEBAR_COLLAPSED
        self._collapsed = False
        self._buttons: dict[str, QPushButton] = {}
        self._labels: dict[str, str] = {}
        self._badges: dict[str, int] = {}
        self._section_labels: list[QLabel] = []
        self.setFixedWidth(self.expanded_width)

        root = QVBoxLayout(self); root.setContentsMargins(10, 14, 10, 10); root.setSpacing(6)
        header = QFrame(); header.setObjectName("sidebar_header"); header_layout = QHBoxLayout(header); header_layout.setContentsMargins(4, 0, 4, 8); header_layout.setSpacing(10)
        self.lbl_brand_icon = QLabel("SP"); self.lbl_brand_icon.setObjectName("lbl_brand_icon"); self.lbl_brand_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_text = QWidget(); brand_text.setObjectName("sidebar_brand_text"); brand_text.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False); brand_text.setAutoFillBackground(False)
        brand_layout = QVBoxLayout(brand_text); brand_layout.setContentsMargins(0,0,0,0); brand_layout.setSpacing(0)
        self.lbl_app_name = QLabel("SP Telegram"); self.lbl_app_name.setObjectName("lbl_app_name"); self.lbl_app_name.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False); self.lbl_app_name.setAutoFillBackground(False)
        self.lbl_edition = QLabel(""); self.lbl_edition.setProperty("muted", True); self.lbl_edition.hide()
        brand_layout.addWidget(self.lbl_app_name)
        header_layout.addWidget(self.lbl_brand_icon); header_layout.addWidget(brand_text, 1)
        self._brand_text = brand_text
        root.addWidget(header)

        self.btn_toggle_sidebar = QPushButton()
        self.btn_toggle_sidebar.setObjectName("btn_toggle_sidebar")
        self.btn_toggle_sidebar.setProperty("role", "ghost")
        self.btn_toggle_sidebar.setIcon(IconManager.get("collapse")); self.btn_toggle_sidebar.setIconSize(IconManager.size())
        self.btn_toggle_sidebar.setToolTip("Collapse sidebar")
        self.btn_toggle_sidebar.clicked.connect(self.toggle)
        root.addWidget(self.btn_toggle_sidebar)

        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame); scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Keep the sidebar surface visible through the navigation scroll area.
        # NOTE: an inline stylesheet on the scroll area breaks QPushButton background
        # rendering (checked/hover) in PySide6 — transparency is handled in the QSS
        # via `QFrame#sidebar QScrollArea { background: transparent; }`.
        scroll.viewport().setAutoFillBackground(False)
        nav_host = QWidget(); nav_host.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False); nav_host.setAutoFillBackground(False)
        nav = QVBoxLayout(nav_host); nav.setContentsMargins(0, 4, 0, 6); nav.setSpacing(2)
        self.group = QButtonGroup(self); self.group.setExclusive(True)
        item_map = {key:(label,obj) for key,label,obj in NAV_ITEMS}
        for key in self.ORDER:
            if key not in item_map: continue
            if key in self.SECTIONS:
                section = QLabel(self.SECTIONS[key]); section.setProperty("navSection", True); self._section_labels.append(section); nav.addWidget(section)
            label, object_name = item_map[key]
            btn = QPushButton(label); btn.setObjectName(object_name); btn.setCheckable(True); btn.setProperty("nav", True)
            btn.setIcon(IconManager.get(self.ICONS.get(key, "dashboard"))); btn.setIconSize(IconManager.size())
            btn.setToolTip(label)
            btn.clicked.connect(lambda checked=False, k=key: self.pageRequested.emit(k, self._labels.get(k, k.replace("_", " ").title())))
            self.group.addButton(btn); self._buttons[key] = btn; self._labels[key] = label; self._badges[key] = 0; nav.addWidget(btn)
        nav.addStretch(); scroll.setWidget(nav_host); root.addWidget(scroll, 1)
        self.set_current("dashboard")

    def _refresh_button(self, key: str) -> None:
        btn = self._buttons.get(key)
        if not btn: return
        label = self._labels.get(key, key.title()); count = self._badges.get(key, 0)
        if self._collapsed:
            btn.setText("")
            btn.setToolTip(f"{label}{f' — {count}' if count else ''}")
        else:
            btn.setText(f"{label}   {count}" if count else label)
            btn.setToolTip(label)

    def set_badge(self, key: str, count: int) -> None:
        if key not in self._buttons: return
        self._badges[key] = max(0, int(count or 0)); self._refresh_button(key)

    def set_current(self, key: str) -> None:
        if key in self._buttons: self._buttons[key].setChecked(True)

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = bool(collapsed)
        self.setFixedWidth(self.compact_width if self._collapsed else self.expanded_width)
        self._brand_text.setVisible(not self._collapsed)
        for label in self._section_labels: label.setVisible(not self._collapsed)
        self.btn_toggle_sidebar.setText("" if self._collapsed else "Collapse")
        self.btn_toggle_sidebar.setIcon(IconManager.get("expand" if self._collapsed else "collapse"))
        self.btn_toggle_sidebar.setToolTip("Expand sidebar" if self._collapsed else "Collapse sidebar")
        self.btn_toggle_sidebar.setProperty("iconButton", self._collapsed)
        for btn in self._buttons.values(): btn.setProperty("collapsed", self._collapsed)
        for key in self._buttons: self._refresh_button(key)
        # Dynamic properties require repolish when a QSS selector depends on them.
        self.style().unpolish(self); self.style().polish(self)
        for btn in self._buttons.values(): btn.style().unpolish(btn); btn.style().polish(btn)
        self.collapsedChanged.emit(self._collapsed)


    def apply_localization(self, localization) -> None:
        for key in self._buttons:
            title, _subtitle = localization.page(key)
            self._labels[key] = title
            self._refresh_button(key)
        for label in self._section_labels:
            label.setText(localization.translate_text(label.text()))
        self.btn_toggle_sidebar.setToolTip(localization.translate_text("Expand sidebar" if self._collapsed else "Collapse sidebar"))
        if not self._collapsed:
            self.btn_toggle_sidebar.setText(localization.translate_text("Collapse"))

    def toggle(self) -> None: self.set_collapsed(not self._collapsed)
    def is_collapsed(self) -> bool: return self._collapsed
