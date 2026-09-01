from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame,QHBoxLayout,QLabel,QVBoxLayout
from app.widgets.avatar_label import AvatarLabel
from app.widgets.status_badge import StatusBadge

class DetailHeaderWidget(QFrame):
    def __init__(self,name:str,subtitle:str="",status:str="",parent=None,*,avatar_service=None,avatar_kind:str="",avatar_id:int=0,avatar_peer_id=None,avatar_account_id:int=0):
        super().__init__(parent); self.setProperty("sectionCard",True)
        root=QHBoxLayout(self); root.setContentsMargins(14,12,14,12); root.setSpacing(12)
        self.lbl_avatar=AvatarLabel(42)
        if avatar_service is not None and avatar_id:
            self.lbl_avatar.set_entity(avatar_service, avatar_kind, avatar_id, name, peer_id=avatar_peer_id, account_id=avatar_account_id)
        else:
            self.lbl_avatar.set_entity(None, "", 0, name)
        text=QVBoxLayout(); text.setContentsMargins(0,0,0,0); text.setSpacing(2); self.lbl_name=QLabel(name or "Unknown"); self.lbl_name.setStyleSheet("font-size:16px;font-weight:650"); self.lbl_subtitle=QLabel(subtitle or ""); self.lbl_subtitle.setProperty("muted",True); text.addWidget(self.lbl_name); text.addWidget(self.lbl_subtitle)
        root.addWidget(self.lbl_avatar); root.addLayout(text,1); self.badge=StatusBadge(status or "Unknown") if status else None
        if self.badge: root.addWidget(self.badge,0,Qt.AlignmentFlag.AlignVCenter)
