from __future__ import annotations

from PySide6.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout
from app.dialogs.dialog_compat import *


class CampaignProgressDialog(QDialog):
    """Non-blocking progress surface for authorized managed-group publishing jobs."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Running Campaign")
        self.setModal(False)
        self.resize(460, 360)
        root = QVBoxLayout(self)
        self.progress_campaign = QProgressBar(); self.progress_campaign.setObjectName("progress_campaign")
        root.addWidget(self.progress_campaign)
        form = QFormLayout()
        self.lbl_campaign_current_target = QLabel("—"); self.lbl_campaign_current_target.setObjectName("lbl_campaign_current_target")
        self.lbl_campaign_target_progress = QLabel("0 / 0"); self.lbl_campaign_target_progress.setObjectName("lbl_campaign_target_progress")
        self.lbl_campaign_message_progress = QLabel("0 / 0"); self.lbl_campaign_message_progress.setObjectName("lbl_campaign_message_progress")
        self.lbl_campaign_success = QLabel("0"); self.lbl_campaign_success.setObjectName("lbl_campaign_success")
        self.lbl_campaign_failed = QLabel("0"); self.lbl_campaign_failed.setObjectName("lbl_campaign_failed")
        self.lbl_campaign_skipped = QLabel("0"); self.lbl_campaign_skipped.setObjectName("lbl_campaign_skipped")
        for label, widget in [("Current", self.lbl_campaign_current_target), ("Targets", self.lbl_campaign_target_progress), ("Messages", self.lbl_campaign_message_progress), ("Success", self.lbl_campaign_success), ("Failed", self.lbl_campaign_failed), ("Skipped", self.lbl_campaign_skipped)]:
            form.addRow(label, widget)
        root.addLayout(form)
        # UX-011: actions bottom-right for consistency with the rest of the app.
        actions=QHBoxLayout(); actions.addStretch(); self.btn_close_progress = QPushButton("Hide"); self.btn_close_progress.clicked.connect(self.hide); actions.addWidget(self.btn_close_progress); root.addLayout(actions)

    def reset_for_campaign(self, campaign_id: int):
        self.setWindowTitle(f"Running Campaign #{campaign_id}")
        self.progress_campaign.setValue(0)
        self.lbl_campaign_current_target.setText("Preparing…")
        for lbl in [self.lbl_campaign_success, self.lbl_campaign_failed, self.lbl_campaign_skipped]: lbl.setText("0")

    def update_progress(self, payload: dict):
        ti = int(payload.get("target_index") or 0); tt = int(payload.get("target_total") or 0)
        mi = int(payload.get("message_index") or 0); mt = int(payload.get("message_total") or 0)
        self.lbl_campaign_current_target.setText(str(payload.get("current_target") or "—"))
        self.lbl_campaign_target_progress.setText(f"{ti} / {tt}")
        self.lbl_campaign_message_progress.setText(f"{mi} / {mt}")
        self.lbl_campaign_success.setText(str(payload.get("success") or 0))
        self.lbl_campaign_failed.setText(str(payload.get("failed") or 0))
        self.lbl_campaign_skipped.setText(str(payload.get("skipped") or 0))
        self.progress_campaign.setValue(int(mi * 100 / max(1, mt)))

# Add compatibility attributes for older PySide6 versions
if not hasattr(CampaignProgressDialog, 'Accepted'):
    CampaignProgressDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(CampaignProgressDialog, 'Rejected'):
    CampaignProgressDialog.Rejected = QDialog.DialogCode.Rejected
