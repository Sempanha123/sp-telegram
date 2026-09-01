from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass(frozen=True)
class InvitationAttemptResult:
    status: str
    error_code: str | None = None
    message: str | None = None
    wait_seconds: int | None = None


class _Control:
    def __init__(self):
        self.resume_event=asyncio.Event();self.resume_event.set();self.stop_requested=False


class TelegramTargetInvitationService:
    """Single-account, sequential direct invitation primitive.

    There is intentionally no account chooser/fallback here.  One caller passes
    one explicit account ID.  FloodWait and permanent privacy/permission errors
    are returned to the orchestration layer and are never retried on another
    account.
    """

    def __init__(self, client_manager, error_handler):
        self.client_manager=client_manager;self.error_handler=error_handler;self._controls={}

    def create_control(self, key:str):
        self._controls[str(key)]=_Control()

    def cleanup(self,key:str):self._controls.pop(str(key),None)
    def pause(self,key:str):
        c=self._controls.get(str(key));
        if c:c.resume_event.clear()
    def resume(self,key:str):
        c=self._controls.get(str(key));
        if c:c.resume_event.set()
    def stop(self,key:str):
        c=self._controls.get(str(key));
        if c:c.stop_requested=True;c.resume_event.set()

    async def checkpoint(self,key:str) -> bool:
        c=self._controls.get(str(key))
        if not c:return True
        await c.resume_event.wait()
        return not c.stop_requested

    async def invite_member(self, account_id:int, entity, telegram_user_id:int, username:str|None=None) -> InvitationAttemptResult:
        client=await self.client_manager.get_client(int(account_id))
        if client is None:return InvitationAttemptResult("FAILED","ACCOUNT_NOT_AUTHORIZED","Selected Telegram account is not connected.")
        try:
            if hasattr(client,"get_input_entity"):
                try:
                    input_user=await client.get_input_entity(int(telegram_user_id))
                except Exception:
                    if not username:
                        raise
                    input_user=await client.get_input_entity(str(username).lstrip("@"))
            else:
                input_user=int(telegram_user_id)
            if hasattr(client,"invite_to_channel"):
                await client.invite_to_channel(entity,[input_user])
            elif type(entity).__name__ == "Chat":
                from telethon.tl.functions.messages import AddChatUserRequest
                await client(AddChatUserRequest(chat_id=int(entity.id),user_id=input_user,fwd_limit=0))
            else:
                from telethon.tl.functions.channels import InviteToChannelRequest
                await client(InviteToChannelRequest(channel=entity,users=[input_user]))
            return InvitationAttemptResult("SUCCESS")
        except Exception as exc:
            name=type(exc).__name__
            permanent={
                "UserPrivacyRestrictedError":("PRIVACY_RESTRICTED","PRIVACY_RESTRICTED","Telegram privacy settings prevent direct invitation."),
                "UserNotMutualContactError":("NOT_MUTUAL","NOT_MUTUAL","Telegram requires a mutual-contact relationship for this invitation."),
                "UserAlreadyParticipantError":("ALREADY_MEMBER","ALREADY_MEMBER","The user is already a member of the target."),
                "UserIdInvalidError":("FAILED","USER_INVALID","The Telegram user is invalid or unavailable."),
                "PeerIdInvalidError":("FAILED","USER_INVALID","The Telegram user cannot be resolved by this account."),
                "UserDeactivatedError":("USER_DEACTIVATED","USER_DEACTIVATED","The Telegram user account is deactivated."),
                "UserDeactivatedBanError":("USER_DEACTIVATED","USER_DEACTIVATED","The Telegram user account is deactivated."),
                "ChatAdminRequiredError":("TARGET_PERMISSION_DENIED","TARGET_PERMISSION_DENIED","The selected account does not have permission to invite users."),
                "ChatWriteForbiddenError":("TARGET_PERMISSION_DENIED","TARGET_PERMISSION_DENIED","Telegram denied invitations for this target."),
            }
            if name in permanent:
                status,code,message=permanent[name];return InvitationAttemptResult(status,code,message)
            try:
                classified=self.error_handler.classify(exc) if self.error_handler else None
            except Exception:
                classified=None
            if classified and classified.code=="FLOOD_WAIT":
                return InvitationAttemptResult("FLOOD_WAIT","FLOOD_WAIT",classified.message,classified.wait_seconds)
            if classified and classified.code in {"PERMISSION_DENIED","PRIVATE_ACCESS_DENIED","NOT_JOINED"}:
                return InvitationAttemptResult("TARGET_PERMISSION_DENIED","TARGET_PERMISSION_DENIED",classified.message)
            if classified:
                return InvitationAttemptResult("FAILED",classified.code,classified.message,classified.wait_seconds)
            return InvitationAttemptResult("FAILED","UNKNOWN","Telegram invitation could not be completed.")
