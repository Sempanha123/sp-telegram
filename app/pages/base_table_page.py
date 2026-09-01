from __future__ import annotations

from typing import Any
import logging

from PySide6.QtCore import QEvent, QSettings, QSortFilterProxyModel, QTimer, Qt, Signal
from PySide6.QtWidgets import QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableView, QVBoxLayout, QWidget

from app.icons import IconManager
from app.models.base_table_model import BaseTableModel
from app.styles.tokens import PAGE_PADDING, TABLE_HEADER_HEIGHT, TABLE_ROW_HEIGHT
from app.widgets.empty_state import EmptyState
from app.widgets.page_header import PageHeaderWidget
from app.widgets.pagination_bar import PaginationBar
from app.widgets.search_bar import SearchBar
from app.widgets.table_delegate import ModernTableDelegate
from app.utils.table_preferences import TablePreferenceManager
from app.utils.table_layout_manager import TableLayoutManager


def _int_setting(manager, name: str, default: int) -> int:
    """Coerce a QSettings-backed preference to an int, falling back to default."""
    value = manager.global_value(name, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


PAGE_SUBTITLES = {
    "Accounts": "Manage authorized Telegram accounts, local metadata and runtime state.",
    "Account Pool": "Manage which authorized accounts are eligible for new jobs, mappings and capabilities.",
    "Account Health": "Review connectivity, authorization, health checks and operational capability.",
    "Restrictions": "Review known restrictions, expiry state and required operator actions.",
    "Sessions": "Inspect authorized Telegram sessions for configured accounts.",
    "Groups": "Manage saved Telegram groups, account mappings and verified permissions.",
    "Source Groups": "Groups selected for later authorized member-data workflows.",
    "Target Groups": "Managed destination groups and known membership state.",
    "Member Pool": "Manage member records, eligibility, tags and exclusions.",
    "Blacklist": "Manage global, Do Not Contact and target-specific exclusions.",
    "Campaigns": "Create and manage authorized campaigns for managed groups and channels.",
    "Jobs": "Track persistent operations, progress, recovery and results.",
    "Alerts": "Review incidents, warnings and items that need operator attention.",
    "Logs": "Monitor application, Telegram, error and audit activity.",
}


class MultiFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent); self.filters: dict[str, str] = {}; self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    def _begin_filter_change(self) -> bool:
        begin = getattr(self, "beginFilterChange", None)
        end = getattr(self, "endFilterChange", None)
        direction = getattr(QSortFilterProxyModel, "Direction", None)
        supported = callable(begin) and callable(end) and direction is not None
        if supported:
            begin()
        return supported
    def _end_filter_change(self, directional: bool) -> None:
        if directional:
            self.endFilterChange(QSortFilterProxyModel.Direction.Rows)
        else:
            # Qt 6.7/6.8 do not expose beginFilterChange/endFilterChange.
            self.invalidateFilter()
    def set_named_filter(self,column_name:str,value:str)->None:
        directional = self._begin_filter_change()
        if value in ("","All"): self.filters.pop(column_name,None)
        else: self.filters[column_name]=value
        self._end_filter_change(directional)
    def clear_named_filters(self) -> None:
        directional = self._begin_filter_change()
        self.filters.clear()
        self._end_filter_change(directional)
    def filterAcceptsRow(self,source_row,source_parent):
        if not super().filterAcceptsRow(source_row,source_parent): return False
        model=self.sourceModel()
        if not isinstance(model,BaseTableModel): return True
        row=model.row_dict(source_row)
        return all(value.lower() in str(row.get(key,"")).lower() for key,value in self.filters.items())


class BaseTablePage(QWidget):
    searchDebounced=Signal(str); filterChanged=Signal(str,str); pageChanged=Signal(int); pageSizeChanged=Signal(int); licenseUpgradeRequested=Signal(str)

    def __init__(self,object_name:str,title:str,model:BaseTableModel,table_object:str,actions:list[tuple[str,str]],search_object:str|None=None,filters:list[tuple[str,str,list[str]]]|None=None,parent=None):
        super().__init__(parent); self.setObjectName(object_name); self._settings=QSettings(); self.table_preferences=TablePreferenceManager(self._settings,self); self.table_layout_manager=TableLayoutManager(self); self._table_preferences_registered=False; self.model=model; self._database_mode=False; self._pending_search=""
        self.proxy=MultiFilterProxyModel(self); self.proxy.setSourceModel(model); self.proxy.setFilterKeyColumn(-1)
        self._search_timer=QTimer(self); self._search_timer.setSingleShot(True); self._search_timer.setInterval(320); self._search_timer.timeout.connect(self._apply_search)
        root=QVBoxLayout(self); self.root_layout=root; root.setContentsMargins(PAGE_PADDING,PAGE_PADDING,PAGE_PADDING,PAGE_PADDING); root.setSpacing(14); self._license_lock=None; self._feature_locked=False; self._feature_preserve_read_only=False; self._empty_action=None
        self.page_header=PageHeaderWidget(title,PAGE_SUBTITLES.get(title,""),self); self.action_buttons={}
        for obj,text in actions:
            btn=QPushButton(text); btn.setObjectName(obj); self._style_action_button(btn,obj,text); self.action_buttons[obj]=btn; self.page_header.add_action(btn)
        root.addWidget(self.page_header)

        filter_host=QWidget(); self.filter_host=filter_host; filter_host.setObjectName("filter_bar"); filter_row=QHBoxLayout(filter_host); filter_row.setContentsMargins(0,0,0,0); filter_row.setSpacing(8); self.search=None
        if search_object:
            placeholder=f"Search {title.lower()}…" if title not in {"Logs"} else "Search logs…"
            self.search=SearchBar(placeholder); self.search.setObjectName(search_object); self.search.setMinimumWidth(300); self.search.textChanged.connect(self._on_search); filter_row.addWidget(self.search,2)
        self.filter_boxes={}; self.filter_labels={}; self._filter_combos={}; self._active_filters={}
        for obj,column,values in filters or []:
            host=QWidget(); v=QVBoxLayout(host); v.setContentsMargins(0,0,0,0); v.setSpacing(3)
            label=QLabel(column); label.setProperty("muted",True); label.setProperty("filterLabel",True)
            combo=QComboBox(); combo.setObjectName(obj); combo.addItems(["All",*values]); combo.setMinimumWidth(125); combo.currentTextChanged.connect(lambda value,c=column:self._on_filter(c,value))
            v.addWidget(label); v.addWidget(combo); self.filter_boxes[obj]=combo; self.filter_labels[obj]=label; self._filter_combos[column]=combo; setattr(self,obj,combo); filter_row.addWidget(host)
        self.btn_clear_filters=QPushButton("Clear Filters"); self.btn_clear_filters.setObjectName("btn_clear_filters"); self.btn_clear_filters.setProperty("role","ghost"); self.btn_clear_filters.setIcon(IconManager.get("close")); self.btn_clear_filters.setToolTip("Reset all filters to All"); self.btn_clear_filters.hide(); self.btn_clear_filters.clicked.connect(self.clear_filters); filter_row.addWidget(self.btn_clear_filters)
        filter_row.addStretch(); root.addWidget(filter_host)

        self.table=QTableView(); self.table.setObjectName(table_object); self.table.setModel(self.proxy); self.table.setSortingEnabled(True); self.table.setAlternatingRowColors(False); self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection); self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); self.table.setWordWrap(False); self.table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel); self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.verticalScrollBar().setSingleStep(16); self.table.horizontalScrollBar().setSingleStep(28)
        header=self.table.horizontalHeader(); header.setStretchLastSection(False); header.setFixedHeight(TABLE_HEADER_HEIGHT); header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        columns=list(getattr(model,"columns",[]) or [])
        primary=next((i for i,name in enumerate(columns) if str(name).lower() in {"account","group","target","member","campaign","message","title","name"}),None)
        for i,name in enumerate(columns):
            low=str(name).lower()
            if low in {"select","id","status","health","connection","role","type","access"}: header.setSectionResizeMode(i,QHeaderView.ResizeMode.ResizeToContents)
        if primary is not None: header.setSectionResizeMode(primary,QHeaderView.ResizeMode.Stretch)
        elif columns: header.setSectionResizeMode(max(0,len(columns)-1),QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False); self.table.verticalHeader().setDefaultSectionSize(TABLE_ROW_HEIGHT)
        self.table_layout_manager.apply(self.table, columns)
        # TableLayoutManager supplies safe widths/minimums. Re-apply the primary
        # identity column's stretch mode afterwards so compact tables fill the
        # available viewport instead of leaving a blank strip on the right.
        if primary is not None:
            header.setSectionResizeMode(primary, QHeaderView.ResizeMode.Stretch)
        self.table.setItemDelegate(ModernTableDelegate(self.table)); root.addWidget(self.table,1)
        # UX-013: Enter/Return on a selected row behaves like double-click so
        # keyboard-only users can open row details on every table page.
        self.table.installEventFilter(self)
        self.empty_state=EmptyState("No records found","No local records match the current search or filters.",icon_name="search"); self.empty_state.setMinimumHeight(150); self.empty_state.setMaximumHeight(220); root.addWidget(self.empty_state,0,Qt.AlignmentFlag.AlignTop)
        # UX-005/010: loading overlay with spinner, shown while async refreshes run.
        from app.widgets.loading_overlay import LoadingOverlay
        self.loading_overlay=LoadingOverlay(self); self.loading_overlay.hide(); root.addWidget(self.loading_overlay)
        self._auto_fit_timer=QTimer(self);self._auto_fit_timer.setSingleShot(True);self._auto_fit_timer.setInterval(30);self._auto_fit_timer.timeout.connect(self._auto_fit_after_refresh)
        self.model.modelReset.connect(self._update_empty);self.model.modelReset.connect(self._schedule_auto_fit_after_refresh);self._update_empty()
        self.pagination_bar=PaginationBar(self); self.pagination_bar.hide(); root.addWidget(self.pagination_bar); self.pagination_bar.pageChanged.connect(self.pageChanged); self.pagination_bar.pageSizeChanged.connect(self.pageSizeChanged)
        self._restore_header()
        # Delay header-menu/table preference registration until derived pages finish
        # applying their default visibility/width rules.
        QTimer.singleShot(0, self.install_table_preferences)

    @staticmethod
    def _style_action_button(btn: QPushButton,obj:str,text:str):
        lower=f"{obj} {text}".lower()
        if any(k in lower for k in ("delete","remove","revoke","logout","cancel")): btn.setProperty("danger",True)
        elif obj.startswith(("btn_add","btn_create","btn_start","btn_schedule")): btn.setProperty("primary",True)
        elif "more" in lower: btn.setProperty("role","ghost"); btn.setIcon(IconManager.get("more"))
        elif "refresh" in lower: btn.setIcon(IconManager.get("refresh"))
        elif "export" in lower: btn.setIcon(IconManager.get("export"))
        elif "import" in lower: btn.setIcon(IconManager.get("import"))
        if obj.startswith(("btn_add","btn_create")): btn.setIcon(IconManager.get("plus"))

    def set_feature_lock(
        self,
        locked: bool,
        *,
        feature_key=None,
        title: str = "Feature Locked",
        description: str = "",
        required_plan: str = "PRO",
        feature_list=None,
        action_text: str | None = None,
        preserve_read_only: bool = False,
    ) -> None:
        """Apply a license presentation lock without changing page business logic.

        ``locked`` remains the only positional argument for backward compatibility
        with pre-license pages.  All optional presentation metadata is keyword-only
        so future call sites cannot silently drift out of sync with this API.
        """
        if locked and self._license_lock is None:
            try:
                from app.widgets.locked_feature import LockedFeatureWidget
                self._license_lock = LockedFeatureWidget(
                    title, description, required_plan, feature_list, self
                )
                self._license_lock.upgradeRequested.connect(self.licenseUpgradeRequested)
            except Exception as exc:
                # A presentation-only license widget must never prevent a page
                # or MainWindow from being constructed.  Record the defect and
                # fall back to a simple read-only lock notice.
                logging.getLogger(__name__).exception("Could not build license feature-lock widget: %s", exc)
                self._license_lock = QLabel(f"{title} — {description}".strip(" —"), self)
                self._license_lock.setWordWrap(True)
                self._license_lock.setProperty("warning", True)
            self.root_layout.insertWidget(1, self._license_lock, 0)

        if self._license_lock is not None:
            self._license_lock.setVisible(bool(locked))
            setattr(self._license_lock, "required_plan", required_plan)
            if feature_key is not None:
                self._license_lock.setProperty("feature_key", str(feature_key))
            if action_text:
                button = getattr(self._license_lock, "btn_upgrade", None)
                if button is not None:
                    button.setText(action_text)

        self._feature_locked=bool(locked)
        self._feature_preserve_read_only=bool(preserve_read_only)
        show_data = (not locked) or bool(preserve_read_only)
        self.filter_host.setVisible(show_data)
        self.table.setVisible(show_data and self.model.rowCount() > 0)
        self.empty_state.setVisible(show_data and self.model.rowCount() == 0)
        self.pagination_bar.setVisible(show_data and self._database_mode)
        for btn in self.action_buttons.values():
            btn.setEnabled(not locked)

    def enable_database_mode(self,state=None):
        self._database_mode=True
        if (not self._feature_locked) or self._feature_preserve_read_only: self.pagination_bar.show()
        if state is not None:self.pagination_bar.set_state(state)
    def update_pagination(self,state): self.pagination_bar.set_state(state); self._update_empty()
    def set_empty_state(self,title:str,description:str):
        self._empty_title=title; self._empty_description=description
        self.empty_state.lbl_title.setText(title); self.empty_state.lbl_description.setText(description); self._update_empty()
    def _has_active_filters(self)->bool:
        return bool(self._active_filters) or bool(self._pending_search) or bool(self.search and self.search.text())
    def _update_empty(self):
        show_data=(not self._feature_locked) or self._feature_preserve_read_only
        empty=self.model.rowCount()==0
        if empty and self._has_active_filters():
            self.empty_state.lbl_title.setText("No results match your filters")
            self.empty_state.lbl_description.setText("Try adjusting or clearing the active filters to see more records.")
            self.empty_state.set_action("Clear Filters", self.clear_filters)
        elif empty:
            self.empty_state.lbl_title.setText(getattr(self,"_empty_title","No records found"))
            self.empty_state.lbl_description.setText(getattr(self,"_empty_description","No local records match the current search or filters."))
            if getattr(self,"_empty_action",None):
                action = getattr(self, "_empty_action", None)
                if action:
                    self.empty_state.set_action(*action)
            elif self.empty_state.btn_action is not None:
                self.empty_state.btn_action.hide()
        self.empty_state.setVisible(show_data and empty)
        self.table.setVisible(show_data and not empty)
        if self._database_mode:
            self.pagination_bar.setVisible(show_data)
    def _on_search(self,text:str): self._pending_search=text; self._search_timer.start()
    def _apply_search(self):
        if self._database_mode: self.proxy.setFilterFixedString(""); self.searchDebounced.emit(self._pending_search)
        else:self.proxy.setFilterFixedString(self._pending_search)
        self._update_empty()
    def _on_filter(self,column:str,value:str):
        if self._database_mode: self.proxy.set_named_filter(column,""); self.filterChanged.emit(column,value)
        else:self.proxy.set_named_filter(column,value)
        if value in ("","All"): self._active_filters.pop(column,None)
        else: self._active_filters[column]=value
        self._refresh_filter_ui()
    def _refresh_filter_ui(self):
        for combo in self.filter_boxes.values():
            active=combo.currentText() not in ("","All")
            combo.setProperty("active",active)
            combo.style().unpolish(combo); combo.style().polish(combo)
        self.btn_clear_filters.setVisible(bool(self._active_filters))
        self._update_empty()
    def clear_filters(self):
        for combo in self.filter_boxes.values():
            combo.blockSignals(True); combo.setCurrentIndex(0); combo.blockSignals(False)
        columns=list(self._active_filters.keys()); self._active_filters.clear()
        if self._database_mode:
            for column in columns: self.filterChanged.emit(column,"All")
        else:
            self.proxy.clear_named_filters()
        self._refresh_filter_ui()
    def eventFilter(self,obj,event):
        if obj is self.table and event.type()==QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            indexes=self.table.selectionModel().selectedRows()
            if indexes:
                self.table.doubleClicked.emit(indexes[0]); return True
        return super().eventFilter(obj,event)
    def set_loading(self,loading:bool,message:str="Loading…"):
        if loading: self.loading_overlay.start(message)
        else: self.loading_overlay.stop()
    def selected_item(self):
        indexes=self.table.selectionModel().selectedRows()
        if not indexes:return None
        return self.model.row_item(self.proxy.mapToSource(indexes[0]).row())
    def selected_items(self):
        indexes=self.table.selectionModel().selectedRows(); return [self.model.row_item(self.proxy.mapToSource(i).row()) for i in indexes]
    def selected_row(self)->dict[str,Any]|None:
        indexes=self.table.selectionModel().selectedRows()
        if not indexes:return None
        return self.model.row_dict(self.proxy.mapToSource(indexes[0]).row())
    def install_table_preferences(self, default_visibility=None, default_widths=None):
        if self._table_preferences_registered:
            return
        columns=list(getattr(self.model,"columns",[]) or [])
        defaults=dict(default_visibility or {})
        for i,column in enumerate(columns):
            defaults.setdefault(column, not self.table.isColumnHidden(i))
        widths=dict(default_widths or {})
        for i,column in enumerate(columns):
            current=self.table.columnWidth(i)
            if current>0: widths.setdefault(column,current)
        table_key=self.table.objectName();first_layout=not self.table_preferences.has_saved_layout(table_key)
        self.table_preferences.register(self.table,columns,default_visibility=defaults,default_widths=widths)
        self._table_preferences_registered=True
        self._apply_scroll_preferences()
        if first_layout and bool(self.table_preferences.global_value("auto_fit_first_open",False)):
            QTimer.singleShot(0,self.auto_fit_columns)

    def _apply_scroll_preferences(self):
        smooth=bool(self.table_preferences.global_value("smooth_scrolling",True))
        mode=QAbstractItemView.ScrollMode.ScrollPerPixel if smooth else QAbstractItemView.ScrollMode.ScrollPerItem
        self.table.setVerticalScrollMode(mode);self.table.setHorizontalScrollMode(mode)
        vertical=max(1,min(120,_int_setting(self.table_preferences,"vertical_scroll_step",16)))
        horizontal=max(1,min(160,_int_setting(self.table_preferences,"horizontal_scroll_step",28)))
        self.table.verticalScrollBar().setSingleStep(vertical);self.table.horizontalScrollBar().setSingleStep(horizontal)

    def _schedule_auto_fit_after_refresh(self):
        if bool(self.table_preferences.global_value("auto_fit_on_refresh",False)):
            self._auto_fit_timer.start()

    def _auto_fit_after_refresh(self):
        if bool(self.table_preferences.global_value("auto_fit_on_refresh",False)):
            self.auto_fit_columns()

    def auto_fit_columns(self):
        if not self._table_preferences_registered:
            self.install_table_preferences()
        if self._table_preferences_registered:
            self.table_preferences.auto_fit(self.table.objectName())

    def refresh_table_preferences(self):
        if not self._table_preferences_registered:
            self.install_table_preferences()
        registered=self.table_preferences._registered.get(self.table.objectName())
        if registered:
            table,columns,defaults=registered;self.table_preferences.apply(table,columns,defaults=defaults)
        model=self.model
        if hasattr(model,"set_display_preferences"):
            kwargs={}
            for key in ("mask_telegram_ids","mask_usernames","mask_display_names","mask_phone_numbers"):
                kwargs[key]=bool(self.table_preferences.global_value(key,False if key!="mask_phone_numbers" else True))
            try:model.set_display_preferences(**kwargs)
            except TypeError:
                kwargs.pop("mask_phone_numbers",None); kwargs.pop("mask_display_names",None); model.set_display_preferences(**kwargs)
        density=str(self.table_preferences.global_value("row_density","Comfortable"))
        self.table.verticalHeader().setDefaultSectionSize(40 if density.lower()=="compact" else 44)
        self._apply_scroll_preferences()

    def save_table_state(self):
        if self._table_preferences_registered:
            self.table_preferences.save_header_state(self.table.objectName())
        self._settings.setValue(f"tables/{self.table.objectName()}/header",self.table.horizontalHeader().saveState())
    def _restore_header(self):
        # Keep reading the pre-TablePreferenceManager key for upgrade compatibility.
        state=self._settings.value(f"tables/{self.table.objectName()}/header")
        if state:self.table.horizontalHeader().restoreState(state)
    def hideEvent(self,event):self.save_table_state();super().hideEvent(event)
