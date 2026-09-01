from __future__ import annotations
from app.telegram.models.member_access_result import MemberAccessResult,MemberListAvailability

class TelegramMemberAccessService:
    def __init__(self,client_manager,error_handler):self.client_manager=client_manager;self.error_handler=error_handler
    async def check(self,group_id:int,account_id:int,entity)->MemberAccessResult:
        client=await self.client_manager.get_client(account_id)
        if not client:return MemberAccessResult(group_id,account_id,MemberListAvailability.UNAVAILABLE.value,message="Telegram client is not connected.",error_code="ACCOUNT_NOT_AUTHORIZED")
        try:
            full=None
            if hasattr(client,"get_group_full"):
                full=await client.get_group_full(entity)
            full_chat=getattr(full,"full_chat",full)
            if bool(getattr(full_chat,"participants_hidden",False)):
                return MemberAccessResult(group_id,account_id,MemberListAvailability.HIDDEN.value,getattr(full_chat,"participants_count",None),"Telegram does not expose the complete participant list to this account.")
            estimated=getattr(full_chat,"participants_count",None) or getattr(entity,"participants_count",None)
            # A normalized adapter may explicitly report a partial list; raw Telethon objects simply omit this hint.
            if bool(getattr(full_chat,"participant_list_partial",False)):
                availability=MemberListAvailability.PARTIAL.value
            # Broadcast channels may expose only a limited participant view to non-admin accounts.
            elif bool(getattr(entity,"broadcast",False)) and not bool(getattr(entity,"megagroup",False)):
                availability=MemberListAvailability.PARTIAL.value
            else:
                availability=MemberListAvailability.FULL.value
            # Probe only the participant endpoint; no alternate enumeration or bypass is attempted.
            if hasattr(client,"get_participants"):
                await client.get_participants(entity,limit=1)
            return MemberAccessResult(group_id,account_id,availability,estimated,"Participant access checked.")
        except Exception as exc:
            result=self.error_handler.classify(exc);name=type(exc).__name__
            # Telegram rate limits must remain attached to the explicitly selected
            # account so the caller can pause/cool it down.  Never convert a
            # FloodWait into a generic unavailable state or retry with another account.
            if result.code=="FLOOD_WAIT":
                raise
            if name in {"ChatAdminRequiredError","ParticipantsTooFewError"}:
                return MemberAccessResult(group_id,account_id,MemberListAvailability.HIDDEN.value,message="Telegram does not expose the participant list to this account.",error_code="PARTICIPANT_LIST_HIDDEN")
            if result.code in {"PRIVATE_ACCESS_DENIED","NOT_JOINED","PERMISSION_DENIED"}:
                return MemberAccessResult(group_id,account_id,MemberListAvailability.ACCESS_DENIED.value,message=result.message,error_code="GROUP_ACCESS_DENIED")
            return MemberAccessResult(group_id,account_id,MemberListAvailability.UNAVAILABLE.value,message=result.message,error_code="PARTICIPANT_LIST_UNAVAILABLE")
