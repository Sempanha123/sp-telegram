from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox,QComboBox,QDialog,QFormLayout,QGroupBox,QHBoxLayout,QLabel,QLineEdit,QMessageBox,QPushButton,QVBoxLayout
from app.dialogs.dialog_compat import *

class AddGroupDialog(QDialog):
    """Telegram group resolver/preview dialog. It never calls Telethon directly."""
    def __init__(self,controller,group=None,classification:str|None=None,parent=None):
        super().__init__(parent);self.controller=controller;self.group=group;self.resolved=None;self.setWindowTitle("Edit Group Classification" if group else "Add Telegram Group");self.setMinimumWidth(650)
        root=QVBoxLayout(self);form=QFormLayout();self.cmb_group_account=QComboBox();self.cmb_group_account.setObjectName("cmb_group_account")
        accounts=list(controller.available_accounts())
        for a in accounts:self.cmb_group_account.addItem(f"{a.first_name or a.username or 'Account'}  @{a.username or '—'}",a.id)
        if not accounts:self.cmb_group_account.addItem("No accounts available",None)
        self.le_group_input=QLineEdit();self.le_group_input.setObjectName("le_group_input");self.le_group_input.setPlaceholderText("@username, t.me link, or private invite link")
        self.btn_resolve_group_input=QPushButton("Resolve Group");self.btn_resolve_group_input.setObjectName("btn_resolve_group_input");host=QHBoxLayout();host.addWidget(self.le_group_input,1);host.addWidget(self.btn_resolve_group_input)
        form.addRow("Account",self.cmb_group_account);form.addRow("Group Username / Link",host);root.addLayout(form)
        preview=QGroupBox("Group Preview");pf=QFormLayout(preview);self.labels={}
        for key,label in [("title","Name"),("username","Username"),("type","Type"),("access","Access"),("members","Members"),("role","Account Role"),("post","Can Post"),("invite","Can Invite"),("manage","Can Manage"),("join","Invite Status")]:
            w=QLabel("—");w.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse);self.labels[key]=w;pf.addRow(label,w)
        root.addWidget(preview)
        flags=QHBoxLayout();self.chk_group_managed=QCheckBox("Managed Group");self.chk_group_managed.setObjectName("chk_group_managed");self.chk_group_source=QCheckBox("Source Group");self.chk_group_source.setObjectName("chk_group_source");self.chk_group_target=QCheckBox("Target Group");self.chk_group_target.setObjectName("chk_group_target");flags.addWidget(self.chk_group_managed);flags.addWidget(self.chk_group_source);flags.addWidget(self.chk_group_target);flags.addStretch();root.addLayout(flags)
        if classification=="source":self.chk_group_source.setChecked(True)
        if classification=="target":self.chk_group_target.setChecked(True)
        self.btn_join_private_group=QPushButton("Join Private Group");self.btn_join_private_group.setObjectName("btn_join_private_group");self.btn_join_private_group.hide();root.addWidget(self.btn_join_private_group)
        actions=QHBoxLayout();actions.addStretch();self.btn_add_resolved_group=QPushButton("Save Group");self.btn_add_resolved_group.setObjectName("btn_add_resolved_group");self.btn_add_resolved_group.setProperty("primary",True);self.btn_cancel_add_group=QPushButton("Cancel");self.btn_cancel_add_group.setObjectName("btn_cancel_add_group");actions.addWidget(self.btn_add_resolved_group);actions.addWidget(self.btn_cancel_add_group);root.addLayout(actions)
        self.btn_resolve_group_input.clicked.connect(self.resolve);self.btn_join_private_group.clicked.connect(self.join_private);self.btn_add_resolved_group.clicked.connect(self.save);self.btn_cancel_add_group.clicked.connect(self.reject);self.btn_resolve_group_input.setEnabled(bool(accounts));self.btn_resolve_group_input.setToolTip("Add or connect an authorized Telegram account first." if not accounts else "")
        if group:
            self.le_group_input.setText(f"@{group.username}" if group.username else str(group.telegram_group_id or ""));self.chk_group_source.setChecked(bool(group.is_source));self.chk_group_target.setChecked(bool(group.is_target));self.chk_group_managed.setChecked(bool(group.is_managed));self._show_local(group)
    def _account_id(self):return self.cmb_group_account.currentData()
    def resolve(self):
        if not self._account_id():QMessageBox.warning(self,"Telegram Account","Choose an authorized Telegram account.");return
        if not self.le_group_input.text().strip():self.le_group_input.setFocus();return
        self.btn_resolve_group_input.setEnabled(False);self.btn_resolve_group_input.setText("Resolving…");self.controller.resolve_group(int(self._account_id()),self.le_group_input.text(),self._resolved)
    def _resolved(self,result):
        self.btn_resolve_group_input.setEnabled(True);self.btn_resolve_group_input.setText("Resolve Group");self.resolved=result;self._render(result)
    def _render(self,r):
        p=r.permissions;self.labels["title"].setText(r.title);self.labels["username"].setText(f"@{r.username}" if r.username else "—");self.labels["type"].setText(r.type.replace("_"," ").title());self.labels["access"].setText(r.access_state.replace("_"," ").title());self.labels["members"].setText(f"{r.member_count:,}" if r.member_count is not None else "Unknown");self.labels["role"].setText(r.account_role.replace("_"," ").title());self.labels["post"].setText(self._cap(p.can_post));self.labels["invite"].setText(self._cap(p.can_invite));self.labels["manage"].setText(self._cap(p.can_manage));self.labels["join"].setText(r.join_state.replace("_"," ").title());self.btn_join_private_group.setVisible(r.join_state in {"AVAILABLE","REQUEST_REQUIRED"})
    def _show_local(self,g):
        self.labels["title"].setText(g.title);self.labels["username"].setText(f"@{g.username}" if g.username else "—");self.labels["type"].setText(g.group_type.replace("_"," ").title());self.labels["access"].setText(g.access_state.replace("_"," ").title());self.labels["members"].setText(str(g.member_count));self.labels["role"].setText(g.role.replace("_"," ").title())
    @staticmethod
    def _cap(v):return "Unknown" if v is None else "Yes" if v else "No"
    def join_private(self):
        if not self.resolved or self._account_id() is None:return
        account=self.cmb_group_account.currentText();answer=QMessageBox.question(self,"Join Telegram Group",f"Join this Telegram group using {account}?\n\nGroup: {self.resolved.title}\n\nJoining is explicit and will never happen during resolve/sync/discovery.")
        if answer!=QMessageBox.StandardButton.Yes:return
        self.btn_join_private_group.setEnabled(False);self.controller.join_private_group(int(self._account_id()),self.resolved,self._joined)
    def _joined(self,result):self.btn_join_private_group.setEnabled(True);self.resolved=result;self._render(result)
    def save(self):
        if self.group and self.resolved is None:
            self.controller.update(self.group.id,{"is_source":self.chk_group_source.isChecked(),"is_target":self.chk_group_target.isChecked(),"is_managed":self.chk_group_managed.isChecked()});self.accept();return
        if not self.resolved:QMessageBox.information(self,"Resolve Group","Resolve the Telegram group before saving.");return
        if self.resolved.already_saved:
            existing=self.controller.service.repository.get_by_telegram_id(self.resolved.telegram_group_id)
            box=QMessageBox(self);box.setWindowTitle("Group Already Exists");box.setText("This Telegram group already exists.");box.setInformativeText("Choose whether to open it, update its Telegram metadata, or add/update this account mapping.")
            open_btn=box.addButton("Open Existing",QMessageBox.ButtonRole.ActionRole);update_btn=box.addButton("Update Existing",QMessageBox.ButtonRole.AcceptRole);map_btn=box.addButton("Add Account Mapping",QMessageBox.ButtonRole.AcceptRole);box.addButton(QMessageBox.StandardButton.Cancel);box.exec();clicked=box.clickedButton()
            if clicked is open_btn and existing:
                from app.dialogs.group_details_dialog import GroupDetailsDialog
                GroupDetailsDialog(self.controller,existing.id,self).exec();return
            if clicked is not update_btn and clicked is not map_btn:return
        item=self.controller.save_resolved_group(self.resolved,{"is_source":self.chk_group_source.isChecked(),"is_target":self.chk_group_target.isChecked(),"is_managed":self.chk_group_managed.isChecked()})
        if item:self.accept()

# Add compatibility attributes for older PySide6 versions
if not hasattr(AddGroupDialog, 'Accepted'):
    AddGroupDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(AddGroupDialog, 'Rejected'):
    AddGroupDialog.Rejected = QDialog.DialogCode.Rejected
