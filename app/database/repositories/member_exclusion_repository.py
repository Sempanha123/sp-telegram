from __future__ import annotations
from app.database.repositories.blacklist_repository import BlacklistRepository

class MemberExclusionRepository(BlacklistRepository):
    """Phase 5 domain name for the existing exclusion/blacklist repository."""
    def add_global_blacklist(self,member_id:int,reason=None,notes=None): return self.add_global_exclusion(member_id,reason,notes,"GLOBAL_BLACKLIST")
    def add_do_not_contact(self,member_id:int,reason=None,notes=None): return self.add_global_exclusion(member_id,reason,notes,"DO_NOT_CONTACT")
    def is_do_not_contact(self,member_id:int): return self.db.fetch_one("SELECT 1 FROM member_exclusions WHERE member_id=? AND exclusion_type='DO_NOT_CONTACT' AND target_group_id IS NULL LIMIT 1",(member_id,)) is not None
