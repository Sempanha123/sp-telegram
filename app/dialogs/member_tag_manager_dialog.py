from __future__ import annotations
from PySide6.QtWidgets import QDialog,QHBoxLayout,QInputDialog,QListWidget,QMessageBox,QPushButton,QVBoxLayout
from app.dialogs.dialog_compat import *

class MemberTagManagerDialog(QDialog):
    def __init__(self,controller,member_id:int|None=None,parent=None):
        super().__init__(parent);self.controller=controller;self.member_id=member_id;self.setWindowTitle("Member Tags");self.resize(460,420);root=QVBoxLayout(self);self.list_tags=QListWidget();root.addWidget(self.list_tags,1);row=QHBoxLayout()
        for obj,text,slot in [("btn_create_member_tag","Create",self.create),("btn_edit_member_tag","Edit",self.edit),("btn_delete_member_tag","Delete",self.delete),("btn_assign_member_tag","Assign",self.assign),("btn_remove_member_tag","Remove",self.remove)]:b=QPushButton(text);b.setObjectName(obj);b.clicked.connect(slot);setattr(self,obj,b);row.addWidget(b)
        root.addLayout(row);self.reload();self.btn_assign_member_tag.setEnabled(member_id is not None);self.btn_remove_member_tag.setEnabled(member_id is not None)
    def reload(self):self.list_tags.clear();self.list_tags.addItems(self.controller.tags())
    def selected(self):return self.list_tags.currentItem().text() if self.list_tags.currentItem() else None
    def create(self):
        name,ok=QInputDialog.getText(self,"Create Tag","Name")
        if ok and name.strip():self.controller.create_tag(name.strip());self.reload()
    def edit(self):
        old=self.selected()
        if not old:return
        new,ok=QInputDialog.getText(self,"Rename Tag","Name",text=old)
        if ok and new.strip():self.controller.rename_tag(old,new.strip());self.reload()
    def delete(self):
        name=self.selected()
        if name and QMessageBox.question(self,"Delete Tag",f"Delete tag '{name}'? Tag links will be removed from members.")==QMessageBox.StandardButton.Yes:self.controller.delete_tag(name);self.reload()
    def assign(self):
        name=self.selected()
        if name and self.member_id:self.controller.add_tag(self.member_id,name)
    def remove(self):
        name=self.selected()
        if name and self.member_id:self.controller.remove_tag(self.member_id,name)

# Add compatibility attributes for older PySide6 versions
if not hasattr(MemberTagManagerDialog, 'Accepted'):
    MemberTagManagerDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(MemberTagManagerDialog, 'Rejected'):
    MemberTagManagerDialog.Rejected = QDialog.DialogCode.Rejected
