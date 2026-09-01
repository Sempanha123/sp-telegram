from __future__ import annotations
from PySide6.QtWidgets import QDialog,QFormLayout,QLabel,QProgressBar,QPushButton,QVBoxLayout
from app.dialogs.dialog_compat import *
class BulkGroupSyncDialog(QDialog):
    def __init__(self,controller,group_ids,parent=None):
        super().__init__(parent);self.controller=controller;self.setWindowTitle("Syncing Groups");self.setMinimumWidth(430);root=QVBoxLayout(self);self.progress=QProgressBar();self.progress.setObjectName("progress_group_sync");root.addWidget(self.progress);f=QFormLayout();self.lbl_current=QLabel("—");self.lbl_success=QLabel("0");self.lbl_failed=QLabel("0");f.addRow("Current",self.lbl_current);f.addRow("Success",self.lbl_success);f.addRow("Failed",self.lbl_failed);root.addLayout(f);self.btn_cancel_group_sync=QPushButton("Cancel");self.btn_cancel_group_sync.setObjectName("btn_cancel_group_sync");root.addWidget(self.btn_cancel_group_sync);controller.bulkSyncProgress.connect(self._progress);controller.bulkSyncFinished.connect(self._finished);self.btn_cancel_group_sync.clicked.connect(controller.cancel_bulk_sync);controller.sync_selected_groups(group_ids)
    def _progress(self,done,total,success,failed,current):self.progress.setMaximum(max(1,total));self.progress.setValue(done);self.lbl_current.setText(current);self.lbl_success.setText(str(success));self.lbl_failed.setText(str(failed))
    def _finished(self,success,failed,cancelled):self.progress.setValue(self.progress.maximum());self.lbl_success.setText(str(success));self.lbl_failed.setText(str(failed));self.lbl_current.setText("Cancelled" if cancelled else "Complete");self.btn_cancel_group_sync.setText("Close");self.btn_cancel_group_sync.clicked.disconnect();self.btn_cancel_group_sync.clicked.connect(self.accept)

# Add compatibility attributes for older PySide6 versions
if not hasattr(BulkGroupSyncDialog, 'Accepted'):
    BulkGroupSyncDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(BulkGroupSyncDialog, 'Rejected'):
    BulkGroupSyncDialog.Rejected = QDialog.DialogCode.Rejected
