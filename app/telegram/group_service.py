from __future__ import annotations
class TelegramGroupService:
    """Telegram-only group façade. Persistence remains in app.services.group_service.GroupService."""
    def __init__(self,resolver,discovery,permissions,sync,invites): self.resolver=resolver;self.discovery=discovery;self.permissions=permissions;self.sync=sync;self.invites=invites
    async def resolve_group(self,account_id,input_value): return await self.resolver.resolve(account_id,input_value)
    async def discover_groups(self,account_id): return await self.discovery.discover(account_id)
    async def refresh_permissions(self,account_id,entity): return await self.permissions.get_my_permissions(account_id,entity)
    async def sync_group(self,account_id,reference): return await self.sync.sync(account_id,reference)
    async def join_private_group(self,account_id,resolved): return await self.invites.join(account_id,resolved)
    async def create_invite_link(self,account_id,entity,request_needed=True): return await self.invites.create_invite_link(account_id,entity,request_needed=request_needed)
    async def list_join_requests(self,account_id,entity,limit=100): return await self.invites.list_join_requests(account_id,entity,limit=limit)
    async def respond_join_request(self,account_id,entity,user_id,approved): return await self.invites.respond_join_request(account_id,entity,user_id,approved=approved)
