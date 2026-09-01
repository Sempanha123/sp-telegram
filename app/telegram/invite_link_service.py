from __future__ import annotations

import logging

from app.telegram.group_normalizer import TelegramGroupNormalizer
from app.telegram.models.resolved_group import GroupAccessState, JoinState

_LOG = logging.getLogger(__name__)


class TelegramInviteLinkService:
    """Explicit invite-link and join-request management for authorized groups.

    This service does not invite arbitrary users and does not rotate accounts.
    Each operation uses the account explicitly selected by the application.
    """

    def __init__(self, client_manager, permission_service=None):
        self.client_manager = client_manager
        self.permission_service = permission_service

    async def join(self, account_id: int, resolved_group):
        invite_hash = getattr(resolved_group, "invite_hash", None)
        if not invite_hash:
            raise ValueError("No valid private invite is available for this group.")
        client = await self.client_manager.get_client(account_id)
        if hasattr(client, "import_chat_invite"):
            result = await client.import_chat_invite(invite_hash)
        else:
            from telethon.tl.functions.messages import ImportChatInviteRequest
            result = await client(ImportChatInviteRequest(invite_hash))
        requested = bool(getattr(result, "join_request", False) or getattr(result, "requested", False))
        if requested:
            resolved_group.join_state = JoinState.PENDING.value
            resolved_group.access_state = GroupAccessState.JOIN_REQUEST_PENDING.value
            return resolved_group
        chats = getattr(result, "chats", None) or []
        if not chats:
            resolved_group.join_state = JoinState.ALREADY_JOINED.value
            resolved_group.access_state = GroupAccessState.PRIVATE_MEMBER.value
            return resolved_group
        entity = chats[0]
        full = None
        try:
            if hasattr(client, "get_group_full"):
                full = await client.get_group_full(entity)
            else:
                from telethon.tl import functions, types
                if isinstance(entity, types.Channel):
                    full = await client(functions.channels.GetFullChannelRequest(entity))
                elif isinstance(entity, types.Chat):
                    full = await client(functions.messages.GetFullChatRequest(entity.id))
        except Exception as exc:
            _LOG.debug("Optional Telegram group metadata lookup failed: %s", exc)
        perms = None
        if self.permission_service:
            try:
                perms = await self.permission_service.get_my_permissions(account_id, entity)
            except Exception as exc:
                _LOG.debug("Optional Telegram group metadata lookup failed: %s", exc)
        normalized = TelegramGroupNormalizer.normalize(
            entity, account_id=account_id, permissions=perms, full=full,
            access_state=GroupAccessState.PRIVATE_MEMBER.value,
            join_state=JoinState.ALREADY_JOINED.value,
            raw_reference_type=resolved_group.raw_reference_type,
        )
        normalized.invite_hash = invite_hash
        return normalized

    async def create_invite_link(self, account_id: int, entity, *, request_needed: bool = True,
                                 title: str | None = None, expire_date=None, usage_limit: int | None = None) -> str:
        client = await self.client_manager.get_client(account_id)
        if client is None:
            raise RuntimeError("Telegram client is unavailable for the selected account.")
        title = (title or "SP Telegram").strip()[:32] or "SP Telegram"
        limit = int(usage_limit) if usage_limit not in {None, 0, ""} else None
        if hasattr(client, "export_chat_invite"):
            kwargs={"request_needed":bool(request_needed),"title":title}
            if expire_date is not None:kwargs["expire_date"]=expire_date
            if limit is not None:kwargs["usage_limit"]=limit
            try:
                result = await client.export_chat_invite(entity, **kwargs)
            except TypeError:
                # Compatibility with older/test adapters that only expose the
                # request_needed parameter.  Permission/rate-limit behavior is
                # still handled by the selected account; there is no fallback.
                result = await client.export_chat_invite(entity, request_needed=bool(request_needed))
        else:
            from telethon.tl import functions
            kwargs={"peer":entity,"request_needed":bool(request_needed),"title":title}
            if expire_date is not None:kwargs["expire_date"]=expire_date
            if limit is not None:kwargs["usage_limit"]=limit
            result = await client(functions.messages.ExportChatInviteRequest(**kwargs))
        link = getattr(result, "link", result if isinstance(result, str) else None)
        if not link:
            raise RuntimeError("Telegram did not return an invite link.")
        return str(link)

    async def list_join_requests(self, account_id: int, entity, *, limit: int = 100) -> list[dict]:
        client = await self.client_manager.get_client(account_id)
        if client is None:
            raise RuntimeError("Telegram client is unavailable for the selected account.")
        if hasattr(client, "list_join_requests"):
            return list(await client.list_join_requests(entity, limit=limit))

        from telethon.tl import functions, types
        result = await client(functions.messages.GetChatInviteImportersRequest(
            peer=entity,
            requested=True,
            offset_date=0,
            offset_user=types.InputUserEmpty(),
            limit=max(1, min(100, int(limit))),
        ))
        users = {int(getattr(user, "id", 0)): user for user in (getattr(result, "users", None) or [])}
        rows = []
        for importer in getattr(result, "importers", None) or []:
            uid = int(getattr(importer, "user_id", 0) or 0)
            user = users.get(uid)
            first = getattr(user, "first_name", None) if user else None
            last = getattr(user, "last_name", None) if user else None
            rows.append({
                "user_id": uid,
                "username": getattr(user, "username", None) if user else None,
                "display_name": " ".join(x for x in (first, last) if x).strip() or (f"User {uid}" if uid else "Unknown"),
                "requested_at": str(getattr(importer, "date", "") or ""),
            })
        return rows

    async def respond_join_request(self, account_id: int, entity, user_id: int, *, approved: bool) -> bool:
        client = await self.client_manager.get_client(account_id)
        if client is None:
            raise RuntimeError("Telegram client is unavailable for the selected account.")
        if hasattr(client, "respond_join_request"):
            return bool(await client.respond_join_request(entity, int(user_id), approved=bool(approved)))

        from telethon.tl import functions
        input_user = await client.get_input_entity(int(user_id)) if hasattr(client, "get_input_entity") else int(user_id)
        await client(functions.messages.HideChatJoinRequestRequest(
            peer=entity,
            user_id=input_user,
            approved=bool(approved),
        ))
        return True
