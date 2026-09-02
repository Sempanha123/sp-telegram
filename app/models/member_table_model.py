from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from app.models.base_table_model import BaseTableModel
from app.utils.formatters import format_local_datetime
from app.utils.member_display_formatter import MemberDisplayFormatter, MemberDisplayPreferences

MEMBER_COLUMNS=["Select","ID","Telegram ID","Name","Username","Sources","Eligibility","Consent","Target Status","Blacklist","Bot","Premium","First Seen","Last Seen","Tags"]



class MemberTableModel(BaseTableModel):
    checkedChanged=Signal()
    def __init__(self,rows,parent=None):
        super().__init__(rows,MEMBER_COLUMNS,parent)
        self.privacy_mode=False
        self.mask_telegram_ids=False
        self.mask_usernames=False
        self.mask_display_names=False
        self.target_selected=False
        self.checked_ids=set()


    def data(self,index,role=Qt.ItemDataRole.DisplayRole):
        if index.isValid() and self.columns[index.column()]=="Select":
            item=self.rows[index.row()]
            if role==Qt.ItemDataRole.CheckStateRole:return Qt.CheckState.Checked if int(item.id) in self.checked_ids else Qt.CheckState.Unchecked
            if role==Qt.ItemDataRole.DisplayRole:return ""
            if role==Qt.ItemDataRole.TextAlignmentRole:return int(Qt.AlignmentFlag.AlignCenter)
        if index.isValid() and role==Qt.ItemDataRole.ToolTipRole:
            item=self.rows[index.row()];column=self.columns[index.column()]
            if column in {"Telegram ID","Username","Name"}: return str(self.value_for_column(item,column) or "—")
            if column=="Sources":return getattr(item,"sources","") or "No saved sources"
            if column=="Tags":return getattr(item,"tags","") or "No tags"
            if column=="First Seen":return str(getattr(item,"first_seen_at",None) or "—")
            if column=="Last Seen":return str(getattr(item,"last_seen_at",None) or "—")
        return super().data(index,role)

    def flags(self,index):
        flags=super().flags(index)
        if index.isValid() and self.columns[index.column()]=="Select":return flags|Qt.ItemFlag.ItemIsUserCheckable|Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsSelectable
        return flags

    def setData(self,index,value,role=Qt.ItemDataRole.EditRole):
        if index.isValid() and self.columns[index.column()]=="Select" and role==Qt.ItemDataRole.CheckStateRole:
            mid=int(self.rows[index.row()].id)
            if value==Qt.CheckState.Checked:self.checked_ids.add(mid)
            else:self.checked_ids.discard(mid)
            self.dataChanged.emit(index,index,[Qt.ItemDataRole.CheckStateRole]);self.checkedChanged.emit();return True
        return False

    def set_all_visible_checked(self,checked:bool):
        ids={int(item.id) for item in self.rows if getattr(item,"id",None) is not None}
        if checked:self.checked_ids.update(ids)
        else:self.checked_ids.difference_update(ids)
        if self.rows:
            left=self.index(0,0);right=self.index(len(self.rows)-1,0);self.dataChanged.emit(left,right,[Qt.ItemDataRole.CheckStateRole])
        self.checkedChanged.emit()

    def visible_check_state(self):
        ids={int(item.id) for item in self.rows if getattr(item,"id",None) is not None}
        if not ids or not (ids & self.checked_ids):return Qt.CheckState.Unchecked
        if ids.issubset(self.checked_ids):return Qt.CheckState.Checked
        return Qt.CheckState.PartiallyChecked

    def checked_member_ids(self):return sorted(self.checked_ids)
    def clear_checked(self):
        self.checked_ids.clear()
        if self.rows:self.dataChanged.emit(self.index(0,0),self.index(len(self.rows)-1,0),[Qt.ItemDataRole.CheckStateRole])
        self.checkedChanged.emit()

    def set_privacy_mode(self,enabled:bool):
        self.privacy_mode=bool(enabled); self.layoutChanged.emit()

    def set_display_preferences(self,*,mask_telegram_ids:bool|None=None,mask_usernames:bool|None=None,mask_display_names:bool|None=None):
        if mask_telegram_ids is not None:self.mask_telegram_ids=bool(mask_telegram_ids)
        if mask_usernames is not None:self.mask_usernames=bool(mask_usernames)
        if mask_display_names is not None:self.mask_display_names=bool(mask_display_names)
        self.layoutChanged.emit()

    def set_target_selected(self,selected:bool):
        self.target_selected=bool(selected);self.layoutChanged.emit()

    def _identity_preferences(self):
        return MemberDisplayPreferences(
            mask_telegram_ids=self.mask_telegram_ids, mask_usernames=self.mask_usernames,
            mask_display_names=self.mask_display_names, privacy_mode=self.privacy_mode,
        )

    def value_for_column(self,m,c):
        pref=self._identity_preferences()
        existing=(getattr(m,"existing_target_state","UNKNOWN") or "UNKNOWN").replace("_"," ").title()
        raw_tags=getattr(m,"tags","") or "";tag_items=[x.strip() for x in raw_tags.split(",") if x.strip()]
        compact_tags=("  ".join(tag_items[:2])+(f"  +{len(tag_items)-2}" if len(tag_items)>2 else "")) if tag_items else "—"
        return {
            "Select":"","ID":m.id,
            "Telegram ID":MemberDisplayFormatter.format_telegram_id(m,pref),
            "Username":MemberDisplayFormatter.format_username(m,pref),
            "Name":MemberDisplayFormatter.format_name(m,pref),
            "Sources":getattr(m,"sources","") or "—","Eligibility":str(m.eligibility_status or "UNKNOWN").replace("_"," ").title(),"Consent":str(m.consent_status or "UNKNOWN").replace("_"," ").title(),
            "Target Status":existing if self.target_selected else "—","Blacklist":bool(getattr(m,"is_blacklisted",0)),"Bot":bool(m.is_bot),"Premium":bool(m.is_premium),
            "First Seen":format_local_datetime(m.first_seen_at),"Last Seen":format_local_datetime(m.last_seen_at),"Tags":compact_tags,
        }.get(c,"")
