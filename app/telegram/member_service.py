from __future__ import annotations
class TelegramMemberService:
    def __init__(self,access_service,sync_service,target_service):
        self.access=access_service;self.sync=sync_service;self.target=target_service
