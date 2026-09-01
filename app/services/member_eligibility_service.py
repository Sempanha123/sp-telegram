from __future__ import annotations
from dataclasses import dataclass
from app.utils.formatters import utc_now_iso

@dataclass(slots=True)
class EligibilityResult:
    status: str
    allowed: bool
    reason_code: str
    reason_text: str
    source: str
    evaluated_at: str


class MemberEligibilityEngine:
    """Evaluates local policy metadata only. UNKNOWN is never silently promoted to eligible."""
    def __init__(self,member_repository,exclusion_repository,target_repository):
        self.members=member_repository;self.exclusions=exclusion_repository;self.targets=target_repository
    def evaluate(self,member_id:int,target_group_id:int|None=None)->EligibilityResult:
        member=self.members.get_by_id(member_id)
        if not member:return self._result("INVALID_USER",False,"MEMBER_NOT_FOUND","Member record does not exist.","MEMBER")
        if member.is_deleted:return self._result("DELETED_ACCOUNT",False,"DELETED_ACCOUNT","Telegram account is marked deleted.","TELEGRAM")
        if member.is_bot:return self._result("BOT",False,"BOT","Telegram account is a bot.","TELEGRAM")
        exclusions=self.exclusions.get_member_exclusions(member_id)
        for kind, status, text in (
            ("GLOBAL_BLACKLIST","EXCLUDED","Global blacklist"),
            ("DO_NOT_CONTACT","DO_NOT_CONTACT","Global Do Not Contact"),
            ("PRIVACY_RESTRICTED","PRIVACY_RESTRICTED","Privacy restricted"),
            ("INVALID_USER","INVALID_USER","Invalid user"),
            ("DELETED_ACCOUNT","DELETED_ACCOUNT","Deleted account"),
            ("BOT","BOT","Bot exclusion"),
            ("MANUAL_EXCLUSION","EXCLUDED","Manual exclusion"),
        ):
            if any(x.exclusion_type==kind and x.target_group_id is None for x in exclusions):
                return self._result(status,False,kind,text,"EXCLUSION")
        if target_group_id is not None:
            if any(x.exclusion_type=="TARGET_EXCLUSION" and x.target_group_id==target_group_id for x in exclusions):
                return self._result("EXCLUDED",False,"TARGET_EXCLUSION","Member is excluded from this target only.","EXCLUSION")
            target=self.targets.get_state(member_id,target_group_id)
            if target and target.state in {"MEMBER","ALREADY_MEMBER"}:
                return self._result("ALREADY_MEMBER",False,"ALREADY_MEMBER","Member is already known to be in the selected target.","TARGET_STATE")
        if member.consent_status in {"DECLINED","REVOKED"}:
            return self._result("DO_NOT_CONTACT",False,"CONSENT_"+member.consent_status,"Consent is declined or revoked.","CONSENT")
        status=(member.eligibility_status or "UNKNOWN").upper()
        if status=="ELIGIBLE":return self._result("ELIGIBLE",True,"MANUAL_ELIGIBLE","Member was explicitly marked eligible locally.","MANUAL")
        if status in {"EXCLUDED","DO_NOT_CONTACT","PRIVACY_RESTRICTED","INVALID_USER","DELETED_ACCOUNT","BOT","MANUAL_REVIEW"}:
            return self._result(status,False,"MANUAL_"+status,status.replace("_"," ").title(),"MANUAL")
        return self._result("UNKNOWN",False,"UNKNOWN","Eligibility has not been established.","LOCAL")
    @staticmethod
    def _result(status,allowed,code,text,source):return EligibilityResult(status,allowed,code,text,source,utc_now_iso())
