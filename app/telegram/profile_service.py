from __future__ import annotations

from pathlib import Path

from app.telegram.result import TelegramProfile


class TelegramProfileService:
    def __init__(self, client_manager, session_pool=None) -> None:
        self.client_manager = client_manager
        self.session_pool = session_pool

    async def _ensure_client(self, account_id: int):
        """Return the active client, lazily creating it from the stored session
        when the account has not been connected yet (e.g. avatar downloads).

        The session pool is the app's lazy resource facade: it creates a client
        from the account's session file on demand, so real profile photos can be
        fetched even before the operator manually connects the account.
        """
        client = await self.client_manager.get_client(account_id)
        if client is not None:
            return client
        if self.session_pool is None:
            raise RuntimeError("Account is not connected.")
        return await self.session_pool.ensure_client(account_id)

    @staticmethod
    def normalize(user) -> TelegramProfile:
        if user is None:
            raise RuntimeError("Telegram profile is unavailable.")
        return TelegramProfile(
            telegram_user_id=int(user.id),
            username=getattr(user, "username", None),
            first_name=getattr(user, "first_name", None),
            last_name=getattr(user, "last_name", None),
            phone=getattr(user, "phone", None),
            is_premium=bool(getattr(user, "premium", False)),
        )

    async def get_me(self, account_id: int) -> TelegramProfile:
        client = await self.client_manager.get_client(account_id)
        if client is None:
            raise RuntimeError("Account is not connected.")
        return self.normalize(await client.get_me())

    async def refresh_profile(self, account_id: int) -> TelegramProfile:
        if not await self.client_manager.is_authorized(account_id):
            raise RuntimeError("Account requires Telegram login.")
        return await self.get_me(account_id)

    async def download_profile_photo(self, account_id: int, peer_id: int | None, dest_path: str | Path) -> str | None:
        """Download a profile photo for an account (peer_id None) or a peer (group/member).

        Returns the path the photo was saved to, or None when the entity has no
        profile photo. Raises RuntimeError when the account is not usable.
        """
        client = await self._ensure_client(account_id)
        if not client.is_connected():
            await self.client_manager.connect(account_id)
        if not await client.is_user_authorized():
            raise RuntimeError("Account requires Telegram login.")

        if peer_id:
            try:
                entity = await client.get_entity(int(peer_id))
            except ValueError:
                # Telethon cannot resolve this peer (the entity is not in its
                # cache, e.g. a member this account has never seen). If the peer
                # is the account itself, fall back to the account's own profile;
                # otherwise treat the entity as having no photo so the UI shows
                # initials instead of failing and retrying forever.
                try:
                    me = await client.get_me()
                except Exception:
                    return None
                if me is not None and int(peer_id) == int(me.id):
                    entity = me
                else:
                    return None
        else:
            entity = await client.get_me()

        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        photo = await client.download_profile_photo(entity, file=str(dest))
        if photo is None:
            return None
        return str(dest)
