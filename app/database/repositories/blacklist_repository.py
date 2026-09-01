from __future__ import annotations
from typing import Any
from app.database.repositories.base_repository import BaseRepository
from app.models.entities import MemberExclusion
from app.utils.formatters import utc_now_iso
COLS=("id","member_id","exclusion_type","target_group_id","reason","notes","created_at","updated_at")
class BlacklistRepository(BaseRepository):
    table_name="member_exclusions"; columns=COLS
    def _add(self,member_id:int,kind:str,target_group_id:int|None,reason:str|None=None,notes:str|None=None):
        now=utc_now_iso(); row=self.db.fetch_one("SELECT id FROM member_exclusions WHERE member_id=? AND exclusion_type=? AND target_group_id IS ? LIMIT 1",(member_id,kind,target_group_id))
        if row: return MemberExclusion.from_row(self.find_by_id(int(row["id"])))
        id=self.insert({"member_id":member_id,"exclusion_type":kind,"target_group_id":target_group_id,"reason":reason,"notes":notes,"created_at":now,"updated_at":now}); return MemberExclusion.from_row(self.find_by_id(id))
    def add_global_exclusion(self,member_id:int,reason:str|None=None,notes:str|None=None,exclusion_type:str="GLOBAL_BLACKLIST"): return self._add(member_id,exclusion_type,None,reason,notes)
    def add_target_exclusion(self,member_id:int,target_group_id:int,reason:str|None=None,notes:str|None=None): return self._add(member_id,"TARGET_EXCLUSION",target_group_id,reason,notes)
    def remove_exclusion(self,id:int): return self.delete(id)
    def remove_member_global(self,member_id:int): return self.db.execute("DELETE FROM member_exclusions WHERE member_id=? AND target_group_id IS NULL",(member_id,)).rowcount
    def is_globally_excluded(self,member_id:int): return self.db.fetch_one("SELECT 1 AS found FROM member_exclusions WHERE member_id=? AND target_group_id IS NULL LIMIT 1",(member_id,)) is not None
    def is_global_blacklisted(self,member_id:int): return self.db.fetch_one("SELECT 1 AS found FROM member_exclusions WHERE member_id=? AND exclusion_type='GLOBAL_BLACKLIST' AND target_group_id IS NULL LIMIT 1",(member_id,)) is not None
    def is_excluded_for_target(self,member_id:int,target_group_id:int): return self.db.fetch_one("SELECT 1 AS found FROM member_exclusions WHERE member_id=? AND (target_group_id IS NULL OR target_group_id=?) LIMIT 1",(member_id,target_group_id)) is not None
    def get_member_exclusions(self,member_id:int):
        rows=self.db.fetch_all(f"SELECT {', '.join(COLS)} FROM member_exclusions WHERE member_id=? ORDER BY created_at DESC",(member_id,)); return [MemberExclusion.from_row(r) for r in rows]
    def search_exclusions(self,query:str):
        term=f"%{query.strip()}%"; return self.db.fetch_all("""SELECT x.id,m.telegram_user_id,m.username,m.first_name,m.last_name,x.exclusion_type,x.target_group_id,x.reason,x.notes,x.created_at FROM member_exclusions x JOIN members m ON m.id=x.member_id WHERE m.username LIKE ? OR m.first_name LIKE ? OR m.last_name LIKE ? OR CAST(m.telegram_user_id AS TEXT) LIKE ? ORDER BY x.created_at DESC""",(term,term,term,term))
    def get_page(self,page:int,page_size:int,search:str|None=None):
        params:list[Any]=[]; where=""
        if search: term=f"%{search.strip()}%"; where=" WHERE m.username LIKE ? OR m.first_name LIKE ? OR m.last_name LIKE ? OR CAST(m.telegram_user_id AS TEXT) LIKE ?"; params=[term]*4
        count=self.db.fetch_one("SELECT COUNT(*) AS count FROM member_exclusions x JOIN members m ON m.id=x.member_id"+where,tuple(params)); off=(max(1,page)-1)*page_size
        rows=self.db.fetch_all("""SELECT x.id,x.member_id,m.telegram_user_id,m.username,m.first_name,m.last_name,x.exclusion_type,x.target_group_id,g.title AS target_title,x.reason,x.notes,x.created_at FROM member_exclusions x JOIN members m ON m.id=x.member_id LEFT JOIN groups g ON g.id=x.target_group_id"""+where+" ORDER BY x.created_at DESC LIMIT ? OFFSET ?",(*params,page_size,off)); return rows,int(count["count"] if count else 0)
    def count_all(self): return self.count()

    def add_global_blacklist(self,member_id:int,reason:str|None=None,notes:str|None=None): return self.add_global_exclusion(member_id,reason,notes,"GLOBAL_BLACKLIST")
    def add_do_not_contact(self,member_id:int,reason:str|None=None,notes:str|None=None): return self.add_global_exclusion(member_id,reason,notes,"DO_NOT_CONTACT")
    def is_do_not_contact(self,member_id:int): return self.db.fetch_one("SELECT 1 AS found FROM member_exclusions WHERE member_id=? AND exclusion_type='DO_NOT_CONTACT' AND target_group_id IS NULL LIMIT 1",(member_id,)) is not None
    def get_by_type(self,kind:str,page:int=1,page_size:int=100):
        off=(max(1,page)-1)*page_size;rows=self.db.fetch_all("SELECT x.*,m.telegram_user_id,m.username,m.first_name,m.last_name,g.title target_title FROM member_exclusions x JOIN members m ON m.id=x.member_id LEFT JOIN groups g ON g.id=x.target_group_id WHERE x.exclusion_type=? ORDER BY x.created_at DESC LIMIT ? OFFSET ?",(kind,page_size,off));return rows
