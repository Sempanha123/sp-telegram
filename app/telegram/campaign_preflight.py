from __future__ import annotations
from app.campaign.content_validator import CampaignContentValidator
from app.campaign.template_renderer import CampaignTemplateRenderer
from app.telegram.models.preflight_result import CampaignPreflightResult,TargetPreflightResult

class CampaignPreflightService:
    def __init__(self,account_safety_service=None):self.validator=CampaignContentValidator();self.renderer=CampaignTemplateRenderer();self.account_safety_service=account_safety_service
    def build(self,campaign,targets,messages,accounts_by_id,groups_by_id,mappings_by_key):
        results=[];global_errors=[]
        planned_by_account={}
        for target in targets:
            if target.account_id:planned_by_account[int(target.account_id)]=planned_by_account.get(int(target.account_id),0)+len(messages)
        if not getattr(campaign,'name','').strip():global_errors.append('Campaign name is required.')
        if not messages:global_errors.append('At least one campaign message is required.')
        message_errors=[]
        for msg in messages:
            message_errors.extend(self.validator.validate_message(msg));message_errors.extend(self.renderer.validate(getattr(msg,'body',None)));message_errors.extend(self.renderer.validate(getattr(msg,'caption',None)))
        global_errors.extend(message_errors)
        for target in targets:
            group=groups_by_id.get(target.group_id);account=accounts_by_id.get(target.account_id);mapping=mappings_by_key.get((target.group_id,target.account_id));errors=[];warnings=[];caps={}
            if group is None:errors.append('Target group is missing from the local database.')
            elif not bool(group.is_managed):errors.append('Target is not marked as a managed group.')
            if account is None:errors.append('No posting account is configured for this target.')
            else:
                if not bool(account.is_enabled):errors.append('Posting account is disabled.')
                if not bool(account.enabled_for_operations):errors.append('Posting account is disabled for new operations.')
                if account.authorization_status!='AUTHORIZED':errors.append('Posting account is not authorized.')
                if account.health_status in {'COOLDOWN','RESTRICTED','SESSION_INVALID','LOGIN_REQUIRED','DISABLED'}:errors.append(f'Posting account health is {account.health_status}.')
                if self.account_safety_service is not None:
                    safety=self.account_safety_service.preview(int(target.account_id),'POST',requested=max(1,planned_by_account.get(int(target.account_id),1)),enforce_interval=False)
                    caps.update({'safety_state':safety.state,'post_used_today':safety.used_today,'post_daily_limit':safety.daily_limit,'post_remaining_today':safety.remaining_today})
                    if not safety.allowed:errors.append(safety.message)
                    elif safety.state=='WATCH':warnings.append(f'Account is in Watch mode with {safety.remaining_today} post attempt(s) remaining today.')
            if mapping is None:errors.append('Posting account is not mapped to this group.')
            else:
                caps.update({'post':bool(mapping.can_post),'media':bool(mapping.can_send_media),'view':bool(mapping.can_view)})
                if not bool(mapping.can_view):errors.append('Posting account does not have verified group access.')
                if not bool(mapping.can_post):errors.append('Posting permission is not verified for this account/group mapping.')
                if any(str(m.message_type).upper()!='TEXT' for m in messages) and not bool(mapping.can_send_media):errors.append('Media permission is not verified for this account/group mapping.')
                if not mapping.last_permission_check_at:warnings.append('Permission data has never been refreshed.')
            results.append(TargetPreflightResult(int(target.group_id),target.account_id,not errors,warnings,errors,caps))
        ready=sum(r.ready for r in results);warn=sum(bool(r.warnings) and r.ready for r in results);blocked=len(results)-ready
        return CampaignPreflightResult(getattr(campaign,'id',None),len(results),ready,warn,blocked,global_errors+[e for r in results for e in r.errors],[w for r in results for w in r.warnings],results)
