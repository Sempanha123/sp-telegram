from __future__ import annotations

from app.telegram.models.target_membership_result import TargetMembershipResult, TargetMembershipStatus


class TelegramTargetMembershipService:
    """Explicit single-account target membership checks.

    UNKNOWN is never treated as NOT_MEMBER.  Permission/privacy errors remain
    distinct so target preparation can safely exclude or review them.
    """

    def __init__(self, client_manager, error_handler):
        self.client_manager = client_manager
        self.error_handler = error_handler

    async def check_member(self, member_id: int, target_group_id: int, account_id: int, entity, telegram_user_id: int) -> TargetMembershipResult:
        client = await self.client_manager.get_client(account_id)
        if client is None:
            return TargetMembershipResult(
                member_id, target_group_id, TargetMembershipStatus.UNKNOWN.value, account_id,
                error_code="ACCOUNT_NOT_AUTHORIZED", error_message="Selected account is not connected.",
            )
        try:
            if hasattr(client, "get_participant"):
                result = await client.get_participant(entity, telegram_user_id)
            else:
                result = await client.get_permissions(entity, telegram_user_id)
            if result is None:
                return TargetMembershipResult(member_id, target_group_id, TargetMembershipStatus.UNKNOWN.value, account_id)
            return TargetMembershipResult(member_id, target_group_id, TargetMembershipStatus.ALREADY_MEMBER.value, account_id)
        except Exception as exc:
            name = type(exc).__name__
            classified = self.error_handler.classify(exc)
            if classified.code == "PARTICIPANT_LIST_HIDDEN":
                return TargetMembershipResult(
                    member_id, target_group_id, TargetMembershipStatus.UNKNOWN.value, account_id,
                    error_code="PARTICIPANT_LIST_HIDDEN",
                    error_message="Telegram hides participant details for this group. This member's target status could not be verified; use an invite link or an account with participant access.",
                )
            if name in {"UserNotParticipantError", "ParticipantIdInvalidError"}:
                return TargetMembershipResult(member_id, target_group_id, TargetMembershipStatus.NOT_MEMBER.value, account_id)
            if name in {"UserPrivacyRestrictedError", "PrivacyRestrictedError"}:
                return TargetMembershipResult(
                    member_id, target_group_id, TargetMembershipStatus.PRIVACY_RESTRICTED.value, account_id,
                    error_code="PRIVACY_RESTRICTED", error_message="Telegram privacy settings prevent this membership check.",
                )
            if classified.code in {"PRIVATE_ACCESS_DENIED", "PERMISSION_DENIED", "NOT_JOINED"}:
                return TargetMembershipResult(
                    member_id, target_group_id, TargetMembershipStatus.ACCESS_DENIED.value, account_id,
                    error_code="GROUP_ACCESS_DENIED", error_message=classified.message,
                )
            if name in {"UserIdInvalidError", "PeerIdInvalidError"}:
                return TargetMembershipResult(
                    member_id, target_group_id, TargetMembershipStatus.INVALID.value, account_id,
                    error_code="USER_INVALID", error_message="Member could not be resolved by the selected account.",
                )
            return TargetMembershipResult(
                member_id, target_group_id, TargetMembershipStatus.ERROR.value, account_id,
                error_code=classified.code, error_message=classified.message,
            )
