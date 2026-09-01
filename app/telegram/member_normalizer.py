from __future__ import annotations
from app.telegram.models.telegram_member import TelegramMember
from app.utils.formatters import utc_now_iso

class TelegramMemberNormalizer:
    def normalize(self,user,source_group_id:int,source_account_id:int)->TelegramMember:
        user_id=getattr(user,"id",None)
        if user_id is None:raise ValueError("Telegram participant does not have a user ID.")
        return TelegramMember(
            telegram_user_id=int(user_id),username=getattr(user,"username",None),first_name=getattr(user,"first_name",None),last_name=getattr(user,"last_name",None),
            is_bot=self._bool_or_none(user,"bot"),is_deleted=self._bool_or_none(user,"deleted"),is_verified=self._bool_or_none(user,"verified"),
            is_scam=self._bool_or_none(user,"scam"),is_fake=self._bool_or_none(user,"fake"),is_premium=self._bool_or_none(user,"premium"),
            source_group_id=source_group_id,source_account_id=source_account_id,observed_at=utc_now_iso(),
        )
    @staticmethod
    def _bool_or_none(obj,name):
        return bool(getattr(obj,name)) if hasattr(obj,name) and getattr(obj,name) is not None else None
