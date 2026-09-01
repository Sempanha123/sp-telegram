from __future__ import annotations
from PySide6.QtCore import QDateTime
from PySide6.QtWidgets import QComboBox,QDateTimeEdit,QDialog,QDialogButtonBox,QFormLayout,QRadioButton,QVBoxLayout
from app.dialogs.dialog_compat import *
from app.widgets.calendar_utils import configure_calendar_popup

class ScheduleDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent); self.setWindowTitle("Schedule Post"); root=QVBoxLayout(self); f=QFormLayout(); self.rb_send_now=QRadioButton("Send Now"); self.rb_send_now.setObjectName("rb_send_now"); self.rb_schedule_once=QRadioButton("Once"); self.rb_schedule_once.setObjectName("rb_schedule_once"); self.rb_schedule_once.setChecked(True); self.rb_schedule_repeat=QRadioButton("Repeat"); self.rb_schedule_repeat.setObjectName("rb_schedule_repeat"); self.dt_schedule_at=QDateTimeEdit(QDateTime.currentDateTime().addSecs(3600)); self.dt_schedule_at.setObjectName("dt_schedule_at"); configure_calendar_popup(self.dt_schedule_at); self.cmb_repeat_type=QComboBox(); self.cmb_repeat_type.setObjectName("cmb_repeat_type"); self.cmb_repeat_type.addItems(["Daily","Weekly","Custom"]); f.addRow(self.rb_send_now); f.addRow(self.rb_schedule_once); f.addRow(self.rb_schedule_repeat); f.addRow("At",self.dt_schedule_at); f.addRow("Repeat",self.cmb_repeat_type); root.addLayout(f); box=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); box.accepted.connect(self.accept); box.rejected.connect(self.reject); root.addWidget(box)

# Add compatibility attributes for older PySide6 versions
if not hasattr(ScheduleDialog, 'Accepted'):
    ScheduleDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(ScheduleDialog, 'Rejected'):
    ScheduleDialog.Rejected = QDialog.DialogCode.Rejected
