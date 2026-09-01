from __future__ import annotations

from contextlib import nullcontext

from app.telegram.message_normalizer import TelegramMessageNormalizer


class CampaignSender:
    def __init__(self, messaging_service, resource_locks=None):
        self.messaging_service = messaging_service
        self.normalizer = TelegramMessageNormalizer()
        self.resource_locks = resource_locks

    async def send(self, account_id: int, group, message, *, schedule_at=None):
        normalized = self.normalizer.normalize(message)
        peer = getattr(group, "username", None) or int(group.telegram_group_id)
        lock = (
            self.resource_locks.hold("ACCOUNT", account_id, "CAMPAIGN_SEND", "Campaign Sender")
            if self.resource_locks else nullcontext()
        )
        with lock:
            return await self.messaging_service.send_message(
                account_id, int(group.id), peer, normalized, schedule_at=schedule_at
            )
