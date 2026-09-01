from __future__ import annotations

from app.telegram.result import TelegramErrorCategory, TelegramErrorResult


class LoginPersistenceError(RuntimeError):
    """Telegram authorization succeeded but local database persistence failed."""


class TelegramErrorHandler:
    """Central Telethon exception classifier with user-safe messages."""

    def classify(self, error: Exception) -> TelegramErrorResult:
        name = type(error).__name__
        wait_seconds = getattr(error, "seconds", None)
        mappings: dict[str, TelegramErrorResult] = {
            "PhoneNumberInvalidError": TelegramErrorResult("PHONE_INVALID", TelegramErrorCategory.AUTH, "The phone number is invalid.", requires_user_action=True),
            "PhoneNumberBannedError": TelegramErrorResult("PHONE_UNAVAILABLE", TelegramErrorCategory.AUTH, "Telegram reports that this phone number cannot currently be used for login.", requires_user_action=True),
            "PhoneNumberFloodError": TelegramErrorResult("LOGIN_RATE_LIMIT", TelegramErrorCategory.RATE_LIMIT, "Telegram is limiting login attempts for this phone number. Wait for Telegram to allow another login attempt before trying again.", requires_user_action=True),
            "PhonePasswordFloodError": TelegramErrorResult("LOGIN_RATE_LIMIT", TelegramErrorCategory.RATE_LIMIT, "Telegram is limiting password attempts for this account. Wait before trying again.", requires_user_action=True),
            "PhoneCodeInvalidError": TelegramErrorResult("CODE_INVALID", TelegramErrorCategory.AUTH, "Verification code is invalid. Please check the code and try again.", requires_user_action=True),
            "PhoneCodeExpiredError": TelegramErrorResult("CODE_EXPIRED", TelegramErrorCategory.AUTH, "Verification code has expired. Request a new code.", requires_user_action=True),
            "SessionPasswordNeededError": TelegramErrorResult("PASSWORD_REQUIRED", TelegramErrorCategory.AUTH, "Two-step verification password is required.", requires_user_action=True),
            "PasswordHashInvalidError": TelegramErrorResult("PASSWORD_INVALID", TelegramErrorCategory.AUTH, "The two-step verification password is incorrect.", requires_user_action=True),
            "ApiIdInvalidError": TelegramErrorResult("API_INVALID", TelegramErrorCategory.CONFIGURATION, "Telegram API credentials are invalid.", requires_user_action=True),
            "AuthKeyUnregisteredError": TelegramErrorResult("SESSION_UNAUTHORIZED", TelegramErrorCategory.SESSION, "This Telegram session is no longer authorized.", requires_login=True, requires_user_action=True),
            "AuthKeyError": TelegramErrorResult("SESSION_INVALID", TelegramErrorCategory.SESSION, "The Telegram session is invalid and requires login again.", requires_login=True, requires_user_action=True),
            "AuthKeyNotFound": TelegramErrorResult("SESSION_INVALID", TelegramErrorCategory.SESSION, "The Telegram session could not be restored.", requires_login=True, requires_user_action=True),
            "UserDeactivatedBanError": TelegramErrorResult("ACCOUNT_UNAVAILABLE", TelegramErrorCategory.AUTH, "Telegram reports that this account cannot be used.", requires_user_action=True),
        }
        if name in {"FloodWaitError", "FloodError", "FloodPremiumWaitError"}:
            return TelegramErrorResult(
                "FLOOD_WAIT", TelegramErrorCategory.RATE_LIMIT,
                "Telegram requested a cooldown. The operation has been stopped and will not be moved to another account.",
                retryable=False, wait_seconds=int(wait_seconds or 0) or None, requires_user_action=True,
            )
        if name in mappings:
            return mappings[name]
        message = str(error or "").lower()
        if (
            "chatparticipantsforbidden" in name.lower()
            or "chatparticipantsforbidden" in message
            or (isinstance(error, AttributeError) and "participants" in message)
        ):
            return TelegramErrorResult(
                "PARTICIPANT_LIST_HIDDEN", TelegramErrorCategory.PERMISSION,
                "Telegram hides participant details for this group. Use an invite link or an account with participant access.",
                requires_user_action=True,
            )
        if isinstance(error, (ConnectionError, TimeoutError, OSError)):
            return TelegramErrorResult("NETWORK_ERROR", TelegramErrorCategory.NETWORK, "Telegram is currently unreachable from this computer.", retryable=True)
        if name in {"ServerError", "RpcCallFailError", "TimedOutError"}:
            return TelegramErrorResult("SERVER_ERROR", TelegramErrorCategory.SERVER, "Telegram returned a temporary server error.", retryable=True)
        group_errors = {
            "UsernameNotOccupiedError": ("USERNAME_NOT_FOUND", "Telegram username was not found. Check the username or link and try again."),
            "UsernameInvalidError": ("INVALID_USERNAME", "The Telegram username is invalid."),
            "InviteHashInvalidError": ("INVALID_INVITE", "This Telegram invite link is invalid."),
            "InviteHashExpiredError": ("INVITE_EXPIRED", "This Telegram invite link is no longer valid."),
            "ChannelPrivateError": ("PRIVATE_ACCESS_DENIED", "This account does not currently have access to the selected private group."),
            "UserNotParticipantError": ("NOT_JOINED", "This account is not currently a member of the selected group."),
            "InviteRequestSentError": ("JOIN_REQUEST_PENDING", "Join request submitted. Waiting for administrator approval."),
            "ChannelInvalidError": ("GROUP_UNAVAILABLE", "The Telegram group is unavailable to this account."),
            "ChatIdInvalidError": ("GROUP_UNAVAILABLE", "The Telegram group is unavailable."),
        }
        if name in group_errors:
            code, message = group_errors[name]
            return TelegramErrorResult(code, TelegramErrorCategory.PERMISSION if code in {"PRIVATE_ACCESS_DENIED","NOT_JOINED"} else TelegramErrorCategory.UNKNOWN, message, requires_user_action=True)
        member_errors = {
            "ParticipantsTooFewError": ("PARTICIPANT_LIST_HIDDEN", "Telegram does not expose the complete participant list to this account."),
            "ParticipantIdInvalidError": ("MEMBER_NOT_FOUND", "The selected Telegram member was not found in this group."),
            "UserIdInvalidError": ("USER_INVALID", "The selected Telegram user is invalid or unavailable."),
            "PeerIdInvalidError": ("USER_INVALID", "The selected Telegram user cannot be resolved by this account."),
        }
        if name in member_errors:
            code, message = member_errors[name]
            return TelegramErrorResult(code, TelegramErrorCategory.PERMISSION if code == "PARTICIPANT_LIST_HIDDEN" else TelegramErrorCategory.UNKNOWN, message, requires_user_action=True)
        campaign_errors = {
            "ChatWriteForbiddenError": ("POST_PERMISSION_DENIED", TelegramErrorCategory.PERMISSION, "This account cannot currently post to the selected group."),
            "ChatSendMediaForbiddenError": ("MEDIA_PERMISSION_DENIED", TelegramErrorCategory.MEDIA, "This account cannot currently send media to the selected group."),
            "MediaInvalidError": ("MEDIA_UPLOAD_FAILED", TelegramErrorCategory.MEDIA, "Telegram rejected the selected media file."),
            "PhotoInvalidDimensionsError": ("MEDIA_UPLOAD_FAILED", TelegramErrorCategory.MEDIA, "Telegram rejected the image dimensions."),
            "VideoContentTypeInvalidError": ("MEDIA_UPLOAD_FAILED", TelegramErrorCategory.MEDIA, "Telegram rejected the video media type."),
            "MessageTooLongError": ("MESSAGE_INVALID", TelegramErrorCategory.CONTENT, "The message is too long for Telegram."),
            "MessageEmptyError": ("MESSAGE_INVALID", TelegramErrorCategory.CONTENT, "The message is empty or invalid."),
            "ScheduleDateTooLateError": ("SCHEDULE_TOO_LATE", TelegramErrorCategory.SCHEDULE, "The scheduled time is too far in the future for Telegram."),
            "ScheduleTooMuchError": ("SCHEDULE_TOO_MUCH", TelegramErrorCategory.SCHEDULE, "Telegram reports too many scheduled messages for this chat."),
        }
        if name in campaign_errors:
            code, category, message = campaign_errors[name]
            return TelegramErrorResult(code, category, message, requires_user_action=True)
        if name in {"ChatAdminRequiredError", "ForbiddenError"}:
            return TelegramErrorResult("PERMISSION_DENIED", TelegramErrorCategory.PERMISSION, "Telegram denied this operation for the current account.", requires_user_action=True)
        return TelegramErrorResult("UNKNOWN", TelegramErrorCategory.UNKNOWN, "Telegram operation could not be completed.")
