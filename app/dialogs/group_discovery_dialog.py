from __future__ import annotations
from PySide6.QtCore import QSortFilterProxyModel,Qt
from PySide6.QtWidgets import QCheckBox,QComboBox,QDialog,QHBoxLayout,QLabel,QLineEdit,QPushButton,QTableView,QVBoxLayout,QAbstractItemView
from app.dialogs.dialog_compat import *
from app.models.base_table_model import BaseTableModel

class GroupDiscoveryDialog(QDialog):
    COLUMNS=["Group","Username","Type","Members","Role","Can Post","Can Invite","Already Saved","Status"]
    def __init__(self,controller,parent=None):
        super().__init__(parent);self.controller=controller;self.results=[];self.setWindowTitle("Discover My Groups");self.resize(1000,650);root=QVBoxLayout(self)
        top=QHBoxLayout();top.addWidget(QLabel("Account:"));self.cmb_discovery_account=QComboBox();self.cmb_discovery_account.setObjectName("cmb_discovery_account")
        accounts=list(controller.available_accounts())
        for a in accounts:self.cmb_discovery_account.addItem(f"{a.first_name or a.username or 'Account'} @{a.username or '—'}",a.id)
        if not accounts:self.cmb_discovery_account.addItem("No accounts available",None)
        self.btn_discover_start=QPushButton("Discover Groups");self.btn_discover_start.setObjectName("btn_discover_start");self.btn_discover_refresh=QPushButton("Refresh");self.btn_discover_refresh.setObjectName("btn_discover_refresh");top.addWidget(self.cmb_discovery_account);top.addWidget(self.btn_discover_start);top.addWidget(self.btn_discover_refresh);top.addStretch();root.addLayout(top)
        filters=QHBoxLayout();self.checks=[]
        for text in ["Groups","Supergroups","Channels","Forums"]:c=QCheckBox(text);c.setChecked(True);c.toggled.connect(self._apply_type_filters);self.checks.append(c);filters.addWidget(c)
        self.le_discovery_search=QLineEdit();self.le_discovery_search.setPlaceholderText("Search discovered groups…");filters.addWidget(self.le_discovery_search,1);root.addLayout(filters)
        self.model=BaseTableModel([],self.COLUMNS);self.proxy=QSortFilterProxyModel(self);self.proxy.setSourceModel(self.model);self.proxy.setFilterKeyColumn(-1);self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive);self.table=QTableView();self.table.setModel(self.proxy);self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection);self.table.setSortingEnabled(True);root.addWidget(self.table,1)
        bottom=QHBoxLayout();self.btn_select_all_discovered=QPushButton("Select All");self.btn_select_all_discovered.setObjectName("btn_select_all_discovered");self.btn_clear_discovered_selection=QPushButton("Clear Selection");self.btn_clear_discovered_selection.setObjectName("btn_clear_discovered_selection");self.btn_save_discovered_groups=QPushButton("Save Selected");self.btn_save_discovered_groups.setObjectName("btn_save_discovered_groups");self.btn_save_discovered_groups.setProperty("primary",True);self.btn_discovery_close=QPushButton("Close");self.btn_discovery_close.setObjectName("btn_discovery_close");[bottom.addWidget(x) for x in [self.btn_select_all_discovered,self.btn_clear_discovered_selection]];bottom.addStretch();bottom.addWidget(self.btn_save_discovered_groups);bottom.addWidget(self.btn_discovery_close);root.addLayout(bottom)
        self.btn_discover_start.clicked.connect(self.discover);self.btn_discover_refresh.clicked.connect(self.discover);self.btn_discover_start.setEnabled(bool(accounts));self.btn_discover_refresh.setEnabled(bool(accounts));self.btn_discover_start.setToolTip("Add or connect an authorized Telegram account first." if not accounts else "");self.le_discovery_search.textChanged.connect(self.proxy.setFilterFixedString);self.btn_select_all_discovered.clicked.connect(self.table.selectAll);self.btn_clear_discovered_selection.clicked.connect(self.table.clearSelection);self.btn_save_discovered_groups.clicked.connect(self.save);self.btn_discovery_close.clicked.connect(self.accept)
    def discover(self):
        aid=self.cmb_discovery_account.currentData()
        if not aid:return
        self.btn_discover_start.setEnabled(False);self.btn_discover_start.setText("Discovering…");self.controller.discover_groups(int(aid),self._loaded)
    def _loaded(self,items):
        self.btn_discover_start.setEnabled(True);self.btn_discover_start.setText("Discover Groups");self.results=items;rows=[]
        for r in items:rows.append({"Group":r.title,"Username":f"@{r.username}" if r.username else "—","Type":r.type.replace("_"," ").title(),"Members":r.member_count if r.member_count is not None else "—","Role":r.account_role.replace("_"," ").title(),"Can Post":self._cap(r.permissions.can_post),"Can Invite":self._cap(r.permissions.can_invite),"Already Saved":"Yes" if r.already_saved else "No","Status":"Saved" if r.already_saved else "New"})
        self._all_rows=rows;self._all_items=list(items);self._apply_type_filters()
    def _apply_type_filters(self):
        rows=getattr(self,"_all_rows",[])
        selected={c.text() for c in self.checks if c.isChecked()}
        def include(row):
            t=str(row.get("Type",""))
            if "Forum" in t:return "Forums" in selected
            if "Supergroup" in t or "Gigagroup" in t:return "Supergroups" in selected
            if "Channel" in t:return "Channels" in selected
            return "Groups" in selected
        pairs=[(r,i) for r,i in zip(rows,getattr(self,"_all_items",[])) if include(r)]
        self._filtered_items=[i for r,i in pairs]
        self.model.replace_rows([r for r,i in pairs])
    @staticmethod
    def _cap(v):return "—" if v is None else "Yes" if v else "No"
    def save(self):
        selected=[]
        for index in self.table.selectionModel().selectedRows():
            source=self.proxy.mapToSource(index);selected.append(self._filtered_items[source.row()])
        if selected:self.controller.save_discovered(selected)

# Add compatibility attributes for older PySide6 versions
if not hasattr(GroupDiscoveryDialog, 'Accepted'):
    GroupDiscoveryDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(GroupDiscoveryDialog, 'Rejected'):
    GroupDiscoveryDialog.Rejected = QDialog.DialogCode.Rejected
