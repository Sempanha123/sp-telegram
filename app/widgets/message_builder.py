from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import Signal
from PySide6.QtGui import QTextCharFormat
from PySide6.QtWidgets import (
    QWidget,QVBoxLayout,QFormLayout,QComboBox,QTextEdit,QLineEdit,QPushButton,QHBoxLayout,
    QLabel,QFileDialog,QCheckBox,QMenu,QInputDialog,QMessageBox
)

class MessageBuilderWidget(QWidget):
    changed=Signal()
    previewRequested=Signal(dict)
    def __init__(self,parent=None):
        super().__init__(parent)
        root=QVBoxLayout(self);form=QFormLayout()
        self.cmb_message_type=QComboBox();self.cmb_message_type.setObjectName('cmb_message_type');self.cmb_message_type.addItems(['Text','Photo','Video','Document','Media + Caption'])
        self.cmb_message_parse_mode=QComboBox();self.cmb_message_parse_mode.setObjectName('cmb_message_parse_mode');self.cmb_message_parse_mode.addItems(['Plain','Markdown','HTML'])
        form.addRow('Message Type',self.cmb_message_type);form.addRow('Formatting',self.cmb_message_parse_mode);root.addLayout(form)
        fmt=QHBoxLayout()
        for obj,text,action in [
            ('btn_format_bold','Bold',self._bold),('btn_format_italic','Italic',self._italic),('btn_format_underline','Underline',self._underline),
            ('btn_format_strike','Strike',self._strike),('btn_format_code','Code',self._code),('btn_format_link','Link',self._link),
        ]:
            b=QPushButton(text);b.setObjectName(obj);b.clicked.connect(action);fmt.addWidget(b);setattr(self,obj,b)
        fmt.addStretch();root.addLayout(fmt)
        self.txt_message_body=QTextEdit();self.txt_message_body.setObjectName('txt_message_body');self.txt_message_body.setPlaceholderText('Write campaign text. Variables: {group_name}, {group_username}, {campaign_name}, {date}, {time}')
        root.addWidget(self.txt_message_body,1)
        self.txt_message_caption=QTextEdit();self.txt_message_caption.setObjectName('txt_message_caption');self.txt_message_caption.setPlaceholderText('Media caption');self.txt_message_caption.setMaximumHeight(100);root.addWidget(self.txt_message_caption)
        media=QHBoxLayout();self.le_media_path=QLineEdit();self.le_media_path.setObjectName('le_media_path');self.le_media_path.setReadOnly(True);media.addWidget(self.le_media_path,1)
        self.btn_attach_media=QPushButton('Attach Media');self.btn_attach_media.setObjectName('btn_attach_media');self.btn_clear_media=QPushButton('Clear');self.btn_clear_media.setObjectName('btn_clear_media');self.btn_open_media=QPushButton('Open');self.btn_open_media.setObjectName('btn_open_media');
        for b in [self.btn_attach_media,self.btn_clear_media,self.btn_open_media]:media.addWidget(b)
        root.addLayout(media);self.lbl_media_info=QLabel('No media attached.');self.lbl_media_info.setProperty('muted',True);root.addWidget(self.lbl_media_info)
        bottom=QHBoxLayout();self.chk_disable_link_preview=QCheckBox('Disable Link Preview');self.chk_disable_link_preview.setObjectName('chk_disable_link_preview');bottom.addWidget(self.chk_disable_link_preview)
        self.btn_insert_variable=QPushButton('Insert Variable');self.btn_insert_variable.setObjectName('btn_insert_variable');self.btn_preview_message=QPushButton('Preview');self.btn_preview_message.setObjectName('btn_preview_message');bottom.addStretch();bottom.addWidget(self.btn_insert_variable);bottom.addWidget(self.btn_preview_message);root.addLayout(bottom)
        self.cmb_message_type.currentTextChanged.connect(self._type_changed);self.btn_attach_media.clicked.connect(self._attach);self.btn_clear_media.clicked.connect(self._clear_media);self.btn_open_media.clicked.connect(self._open_media);self.btn_insert_variable.clicked.connect(self._variables);self.btn_preview_message.clicked.connect(lambda:self.previewRequested.emit(self.data()))
        for w in [self.cmb_message_type,self.cmb_message_parse_mode,self.txt_message_body,self.txt_message_caption,self.le_media_path,self.chk_disable_link_preview]:
            signal=getattr(w,'textChanged',None) or getattr(w,'currentTextChanged',None) or getattr(w,'stateChanged',None)
            if signal:signal.connect(lambda *_:self.changed.emit())
        self._type_changed(self.cmb_message_type.currentText())
    def _type_changed(self,text):
        media=text!='Text';self.txt_message_caption.setVisible(media);self.le_media_path.setVisible(media);self.btn_attach_media.setVisible(media);self.btn_clear_media.setVisible(media);self.btn_open_media.setVisible(media);self.lbl_media_info.setVisible(media)
    def _attach(self):
        path,_=QFileDialog.getOpenFileName(self,'Choose campaign media')
        if path:self.le_media_path.setText(path);self._media_info(path);self.changed.emit()
    def _clear_media(self):self.le_media_path.clear();self.lbl_media_info.setText('No media attached.');self.changed.emit()
    def _open_media(self):
        path=self.le_media_path.text().strip()
        if path and Path(path).is_file():
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
    def _media_info(self,path):
        p=Path(path)
        try:size=p.stat().st_size;display=f'{size/1024/1024:.2f} MB' if size>=1024*1024 else f'{size/1024:.1f} KB'
        except OSError:display='Unavailable'
        self.lbl_media_info.setText(f'{p.name} • {display}')
    def _variables(self):
        menu=QMenu(self)
        for token in ['{group_name}','{group_username}','{campaign_name}','{date}','{time}']:
            act=menu.addAction(token);act.triggered.connect(lambda checked=False,t=token:self.txt_message_body.insertPlainText(t))
        menu.exec(self.btn_insert_variable.mapToGlobal(self.btn_insert_variable.rect().bottomLeft()))
    def _wrap_selection(self,prefix,suffix=None):
        suffix=prefix if suffix is None else suffix;cursor=self.txt_message_body.textCursor();text=cursor.selectedText()
        if not text:return
        cursor.insertText(prefix+text+suffix)
    def _bold(self):self._wrap_selection('**')
    def _italic(self):self._wrap_selection('_')
    def _strike(self):self._wrap_selection('~~')
    def _code(self):self._wrap_selection('`')
    def _underline(self):
        if self.cmb_message_parse_mode.currentText()=='HTML':self._wrap_selection('<u>','</u>')
        else:self._wrap_selection('__')
    def _link(self):
        cursor=self.txt_message_body.textCursor();text=cursor.selectedText()
        if not text:return
        url,ok=QInputDialog.getText(self,'Insert Link','URL')
        if ok and url:
            if self.cmb_message_parse_mode.currentText()=='HTML':cursor.insertText(f'<a href="{url}">{text}</a>')
            else:cursor.insertText(f'[{text}]({url})')
    def data(self):
        return {'message_type':self.cmb_message_type.currentText().upper().replace(' ','_').replace('+','WITH'),'type':self.cmb_message_type.currentText(),'body':self.txt_message_body.toPlainText(),'caption':self.txt_message_caption.toPlainText(),'media_path':self.le_media_path.text().strip() or None,'parse_mode':self.cmb_message_parse_mode.currentText().upper(),'disable_link_preview':self.chk_disable_link_preview.isChecked()}
    def set_data(self,data):
        label=str(data.get('type') or data.get('message_type') or 'TEXT').replace('_',' ').replace('WITH','+').title();idx=self.cmb_message_type.findText(label,0)
        if idx<0:
            choices={'MEDIA WITH CAPTION':'Media + Caption'};idx=self.cmb_message_type.findText(choices.get(label.upper(),label))
        if idx>=0:self.cmb_message_type.setCurrentIndex(idx)
        self.txt_message_body.setPlainText(data.get('body') or data.get('text') or '');self.txt_message_caption.setPlainText(data.get('caption') or '');self.le_media_path.setText(data.get('media_path') or data.get('media') or '')
        pm=str(data.get('parse_mode') or 'PLAIN').title();idx=self.cmb_message_parse_mode.findText(pm);self.cmb_message_parse_mode.setCurrentIndex(max(0,idx));self.chk_disable_link_preview.setChecked(bool(data.get('disable_link_preview')))
        if self.le_media_path.text():self._media_info(self.le_media_path.text())
