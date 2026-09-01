from __future__ import annotations
from PySide6.QtWidgets import QDialog,QDialogButtonBox,QMessageBox,QVBoxLayout
from app.dialogs.dialog_compat import *
from app.widgets.message_builder import MessageBuilderWidget

class MessageEditorDialog(QDialog):
    def __init__(self,parent=None,data=None):
        super().__init__(parent);self.setWindowTitle('Message Builder');self.resize(720,620);root=QVBoxLayout(self);self.builder=MessageBuilderWidget(self);root.addWidget(self.builder,1)
        # Compatibility attributes expected by the original UI/spec.
        for name in ['cmb_message_type','txt_message_body','txt_message_caption','le_media_path','btn_attach_media','btn_clear_media','btn_preview_message','btn_insert_variable','cmb_message_parse_mode','chk_disable_link_preview','btn_format_bold','btn_format_italic','btn_format_underline','btn_format_strike','btn_format_code','btn_format_link','btn_open_media']:
            setattr(self,name,getattr(self.builder,name))
        self.builder.previewRequested.connect(self._preview)
        box=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);box.accepted.connect(self.accept);box.rejected.connect(self.reject);root.addWidget(box)
        if data:self.builder.set_data(data)
    def _preview(self,data):
        body=data.get('body') or data.get('caption') or '[Media]';QMessageBox.information(self,'Message Preview',body[:4000] or '[Empty message]')
    def data(self):return self.builder.data()


# Add compatibility attributes for older PySide6 versions
if not hasattr(MessageEditorDialog, 'Accepted'):
    MessageEditorDialog.Accepted = QDialog.DialogCode.Accepted
if not hasattr(MessageEditorDialog, 'Rejected'):
    MessageEditorDialog.Rejected = QDialog.DialogCode.Rejected
