from __future__ import annotations
from app.models.entities import CampaignTemplate
class CampaignTemplateService:
    def __init__(self,repository):self.repository=repository;self.feature_gate=None;self.license_limit_service=None
    def get_all(self):return self.repository.get_all()
    def create(self,data,messages=None,groups=None):
        if self.feature_gate is not None:
            from app.license.feature_keys import FeatureKey
            self.feature_gate.require_feature(FeatureKey.TEMPLATES)
        if self.license_limit_service is not None:
            result=self.license_limit_service.can_create_template()
            if not result.allowed:raise RuntimeError(result.message or "Campaign template plan limit reached.")
        name=(data.get('name') or '').strip()
        if not name:raise ValueError('Template name is required.')
        return self.repository.create(CampaignTemplate(name=name,description=data.get('description'),template_type=str(data.get('template_type') or 'TEXT').upper(),default_parse_mode=str(data.get('default_parse_mode') or 'PLAIN').upper(),default_schedule_type=data.get('default_schedule_type'),default_timezone=data.get('default_timezone')),messages or [],groups or [])
    def update(self,id,data,messages=None,groups=None):
        if self.feature_gate is not None:
            from app.license.feature_keys import FeatureKey
            self.feature_gate.require_feature(FeatureKey.TEMPLATES)
        item=self.repository.get_by_id(id)
        if not item:raise ValueError('Template not found.')
        for f in ('name','description','template_type','default_parse_mode','default_schedule_type','default_timezone'):
            if f in data:setattr(item,f,data[f])
        return self.repository.update(item,messages,groups)
    def duplicate(self,id):
        if self.feature_gate is not None:
            from app.license.feature_keys import FeatureKey
            self.feature_gate.require_feature(FeatureKey.TEMPLATES)
        if self.license_limit_service is not None:
            result=self.license_limit_service.can_create_template()
            if not result.allowed:raise RuntimeError(result.message or "Campaign template plan limit reached.")
        return self.repository.duplicate(id)
    def delete(self,id):return self.repository.delete(id)
    def details(self,id):return {'template':self.repository.get_by_id(id),'messages':self.repository.get_messages(id)}
