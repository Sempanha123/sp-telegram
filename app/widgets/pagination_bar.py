from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox,QFrame,QHBoxLayout,QLabel,QPushButton,QSpinBox
from app.icons import IconManager

class PaginationBar(QFrame):
    pageChanged=Signal(int); pageSizeChanged=Signal(int)
    def __init__(self,parent=None):
        super().__init__(parent); self.setObjectName("pagination_bar"); self._page=1; self._total_pages=1
        layout=QHBoxLayout(self); layout.setContentsMargins(0,3,0,0); layout.setSpacing(8)
        self.lbl_total=QLabel("0 results"); self.lbl_total.setObjectName("lbl_pagination_total")
        self.cmb_page_size=QComboBox(); self.cmb_page_size.setObjectName("cmb_page_size"); self.cmb_page_size.addItems(["50","100","250","500"]); self.cmb_page_size.setCurrentText("100"); self.cmb_page_size.setFixedWidth(74)
        self.btn_previous=QPushButton("Previous"); self.btn_previous.setObjectName("btn_page_previous"); self.btn_previous.setIcon(IconManager.get("chevron_left"))
        # UX-001: editable page-jump spinbox replaces the static "1 / 1" label so
        # users can type a page number instead of clicking Next dozens of times.
        self.spin_page=QSpinBox(); self.spin_page.setObjectName("spin_page_jump"); self.spin_page.setRange(1,1); self.spin_page.setValue(1); self.spin_page.setFixedWidth(64); self.spin_page.setAlignment(Qt.AlignmentFlag.AlignCenter); self.spin_page.setToolTip("Jump to page — type a number and press Enter")
        self.lbl_page_total=QLabel("/ 1"); self.lbl_page_total.setObjectName("lbl_pagination_page")
        self.btn_next=QPushButton("Next"); self.btn_next.setObjectName("btn_page_next"); self.btn_next.setIcon(IconManager.get("chevron_right"))
        layout.addWidget(self.lbl_total); layout.addWidget(QLabel("Rows")); layout.addWidget(self.cmb_page_size); layout.addStretch(); layout.addWidget(self.btn_previous); layout.addWidget(self.spin_page); layout.addWidget(self.lbl_page_total); layout.addWidget(self.btn_next)
        self.btn_previous.clicked.connect(lambda:self.pageChanged.emit(max(1,self._page-1))); self.btn_next.clicked.connect(lambda:self.pageChanged.emit(min(self._total_pages,self._page+1))); self.cmb_page_size.currentTextChanged.connect(lambda v:self.pageSizeChanged.emit(int(v)))
        self.spin_page.valueChanged.connect(self._on_jump)
    def _on_jump(self,value):
        if value!=self._page: self.pageChanged.emit(value)
    def set_state(self,state):
        self._page=int(state.page); self._total_pages=max(1,int(state.total_pages)); self.lbl_page_total.setText(f"/ {self._total_pages}"); self.lbl_total.setText(f"{state.total_items:,} results")
        if self.cmb_page_size.currentText()!=str(state.page_size): self.cmb_page_size.blockSignals(True); self.cmb_page_size.setCurrentText(str(state.page_size)); self.cmb_page_size.blockSignals(False)
        self.spin_page.blockSignals(True); self.spin_page.setRange(1,self._total_pages); self.spin_page.setValue(self._page); self.spin_page.blockSignals(False)
        self.btn_previous.setEnabled(state.page>1); self.btn_next.setEnabled(state.page<self._total_pages)
