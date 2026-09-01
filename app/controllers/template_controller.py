from __future__ import annotations
from PySide6.QtCore import QObject,Signal
class TemplateController(QObject):
    templatesChanged=Signal(list);toast_requested=Signal(str,str);errorOccurred=Signal(str);featureLocked=Signal(str,str);planLimitReached=Signal(str,object)
    def __init__(self,service,parent=None):super().__init__(parent);self.service=service;self.feature_gate=None;self.license_limit_service=None
    def refresh(self):
        try:r=self.service.get_all();self.templatesChanged.emit(r);return r
        except Exception as exc:self._error(exc);return []
    def create(self,data,messages=None,groups=None):
        from app.license.feature_keys import FeatureKey
        if self.feature_gate is not None and not self.feature_gate.has_feature(FeatureKey.TEMPLATES):self.featureLocked.emit(str(FeatureKey.TEMPLATES),str(self.feature_gate.get_required_plan(FeatureKey.TEMPLATES) or "PRO"));return None
        if self.license_limit_service is not None:
            result=self.license_limit_service.can_create_template()
            if not result.allowed:self.planLimitReached.emit("MAX_TEMPLATES",result);return None
        return self._wrap(lambda:self.service.create(data,messages,groups),'Template created.')
    def update(self,id,data,messages=None,groups=None):return self._wrap(lambda:self.service.update(id,data,messages,groups),'Template updated.')
    def duplicate(self,id):
        from app.license.feature_keys import FeatureKey
        if self.feature_gate is not None and not self.feature_gate.has_feature(FeatureKey.TEMPLATES):
            self.featureLocked.emit(str(FeatureKey.TEMPLATES),str(self.feature_gate.get_required_plan(FeatureKey.TEMPLATES) or "PRO"));return None
        if self.license_limit_service is not None:
            result=self.license_limit_service.can_create_template()
            if not result.allowed:self.planLimitReached.emit("MAX_TEMPLATES",result);return None
        return self._wrap(lambda:self.service.duplicate(id),'Template duplicated.')
    def delete(self,id):return self._wrap(lambda:self.service.delete(id),'Template deleted.')
    def details(self,id):return self.service.details(id)
    def _wrap(self,fn,msg):
        try:r=fn();self.refresh();self.toast_requested.emit(msg,'Success');return r
        except Exception as exc:self._error(exc);return None
    def _error(self,exc):m=str(exc) or 'Cannot complete template operation.';self.errorOccurred.emit(m);self.toast_requested.emit(m,'Error')
