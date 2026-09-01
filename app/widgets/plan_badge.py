from __future__ import annotations
from PySide6.QtWidgets import QLabel
class PlanBadge(QLabel):
    def __init__(self,text='',parent=None):
        super().__init__(text,parent);self.setProperty('planBadge',True);self.setProperty('plan',text.upper());self.setMaximumHeight(24)
    def set_plan(self,text):self.setText(text);self.setProperty('plan',str(text).upper());self.style().unpolish(self);self.style().polish(self)
