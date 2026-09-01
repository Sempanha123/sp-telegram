from __future__ import annotations
from dataclasses import asdict
from app.database.repositories.base_repository import BaseRepository
from app.models.entities import GroupAccount
from app.utils.formatters import utc_now_iso

COLS=("id","group_id","account_id","role","access_state","can_view","can_post","can_send_media","can_invite","can_manage","can_delete_messages","can_pin_messages","can_ban_users","can_add_admins","can_manage_call","can_manage_topics","can_manage_invite_links","can_approve_join_requests","is_primary","joined_at","last_access_check_at","last_permission_check_at","last_error_code","last_error_message","member_list_availability","member_list_checked_at","last_member_sync_at","member_sync_status","stored_member_count","last_member_new","last_member_updated","last_member_excluded","created_at","updated_at")
class GroupAccountRepository(BaseRepository):
    table_name="group_accounts";columns=COLS
    def create_mapping(self,item:GroupAccount):return self.upsert_mapping(item)
    def upsert(self,item:GroupAccount):return self.upsert_mapping(item)
    def upsert_mapping(self,item:GroupAccount):
        now=utc_now_iso();data=asdict(item);data.pop("id",None);data={k:v for k,v in data.items() if k in COLS};data["created_at"]=item.created_at or now;data["updated_at"]=now
        names=tuple(data);ph=",".join("?" for _ in names);updates=",".join(f"{n}=excluded.{n}" for n in names if n not in {"group_id","account_id","created_at"})
        self.db.execute(f"INSERT INTO group_accounts({','.join(names)}) VALUES({ph}) ON CONFLICT(group_id,account_id) DO UPDATE SET {updates}",tuple(data[n] for n in names))
        return self.get_mapping(int(item.group_id),int(item.account_id))
    def remove_mapping(self,group_id:int,account_id:int):
        with self.db.transaction():
            existing=self.get_mapping(group_id,account_id)
            removed=self.db.execute("DELETE FROM group_accounts WHERE group_id=? AND account_id=?",(group_id,account_id)).rowcount>0
            if removed and existing and bool(existing.is_primary):
                replacement=self.db.fetch_one("SELECT account_id FROM group_accounts WHERE group_id=? ORDER BY id LIMIT 1",(group_id,))
                if replacement:self.db.execute("UPDATE group_accounts SET is_primary=1,updated_at=? WHERE group_id=? AND account_id=?",(utc_now_iso(),group_id,int(replacement["account_id"])))
        return removed
    def get_mapping(self,group_id:int,account_id:int):return GroupAccount.from_row(self.db.fetch_one(f"SELECT {', '.join(COLS)} FROM group_accounts WHERE group_id=? AND account_id=?",(group_id,account_id)))
    def _joined(self,where,params):
        fields=", ".join("ga."+c for c in COLS)
        rows=self.db.fetch_all(f"""SELECT {fields},COALESCE(a.first_name,a.username,CAST(a.id AS TEXT)) account_name,a.username account_username,a.connection_status,a.health_status
        FROM group_accounts ga JOIN telegram_accounts a ON a.id=ga.account_id WHERE {where} ORDER BY ga.is_primary DESC,ga.id""",params)
        return [GroupAccount.from_row(r) for r in rows]
    def get_for_group(self,group_id:int):return self._joined("ga.group_id=?",(group_id,))
    def get_group_accounts(self,group_id:int):return self.get_for_group(group_id)
    def get_account_groups(self,account_id:int):
        rows=self.db.fetch_all("""SELECT ga.*,g.title group_title,g.username group_username,g.status group_status,g.last_sync_at group_last_sync,g.is_managed
        FROM group_accounts ga JOIN groups g ON g.id=ga.group_id WHERE ga.account_id=? ORDER BY g.title""",(account_id,));return [dict(r) for r in rows]
    def set_primary_account(self,group_id:int,account_id:int):
        with self.db.transaction():
            self.db.execute("UPDATE group_accounts SET is_primary=0,updated_at=? WHERE group_id=?",(utc_now_iso(),group_id))
            cur=self.db.execute("UPDATE group_accounts SET is_primary=1,updated_at=? WHERE group_id=? AND account_id=?",(utc_now_iso(),group_id,account_id))
            if not cur.rowcount:raise ValueError("Account mapping does not exist for this group.")
        return self.get_mapping(group_id,account_id)
    def get_primary_account(self,group_id:int):
        row=self.db.fetch_one(f"SELECT {', '.join(COLS)} FROM group_accounts WHERE group_id=? AND is_primary=1",(group_id,));return GroupAccount.from_row(row)
    def update_role(self,group_id:int,account_id:int,role:str):return self.db.execute("UPDATE group_accounts SET role=?,updated_at=? WHERE group_id=? AND account_id=?",(role,utc_now_iso(),group_id,account_id)).rowcount>0
    def update_permissions(self,group_id:int,account_id:int,permissions):
        values={k:getattr(permissions,k) for k in ("role","can_view","can_post","can_send_media","can_invite","can_manage","can_delete_messages","can_pin_messages","can_ban_users","can_add_admins","can_manage_call","can_manage_topics","can_manage_invite_links","can_approve_join_requests")}
        values={k:(int(v) if isinstance(v,bool) else v) for k,v in values.items()};values["last_permission_check_at"]=getattr(permissions,"checked_at",None) or utc_now_iso();values["last_access_check_at"]=utc_now_iso();values["updated_at"]=utc_now_iso()
        assignments=",".join(f"{k}=?" for k in values);return self.db.execute(f"UPDATE group_accounts SET {assignments} WHERE group_id=? AND account_id=?",(*values.values(),group_id,account_id)).rowcount>0
    def update_access_state(self,group_id:int,account_id:int,state:str):return self.db.execute("UPDATE group_accounts SET access_state=?,last_access_check_at=?,updated_at=? WHERE group_id=? AND account_id=?",(state,utc_now_iso(),utc_now_iso(),group_id,account_id)).rowcount>0
    def update_last_error(self,group_id:int,account_id:int,code:str|None,message:str|None):return self.db.execute("UPDATE group_accounts SET last_error_code=?,last_error_message=?,updated_at=? WHERE group_id=? AND account_id=?",(code,message,utc_now_iso(),group_id,account_id)).rowcount>0
    def mark_verification_unavailable(self,group_id:int,account_id:int,code:str,message:str):
        """Fail closed while a mapping is pending or after verification fails."""
        return self.db.execute("""UPDATE group_accounts SET role='UNKNOWN',access_state='UNAVAILABLE',
            can_view=NULL,can_post=NULL,can_send_media=NULL,can_invite=NULL,can_manage=NULL,
            can_delete_messages=NULL,can_pin_messages=NULL,can_ban_users=NULL,can_add_admins=NULL,
            can_manage_call=NULL,can_manage_topics=NULL,can_manage_invite_links=NULL,can_approve_join_requests=NULL,
            last_access_check_at=NULL,last_permission_check_at=NULL,last_error_code=?,last_error_message=?,updated_at=?
            WHERE group_id=? AND account_id=?""",(code,message,utc_now_iso(),group_id,account_id)).rowcount>0

    def update_member_access(self,group_id:int,account_id:int,availability:str,*,checked_at:str|None=None):
        now=checked_at or utc_now_iso();return self.db.execute("UPDATE group_accounts SET member_list_availability=?,member_list_checked_at=?,updated_at=? WHERE group_id=? AND account_id=?",(availability,now,now,group_id,account_id)).rowcount>0
    def update_member_sync_stats(self,group_id:int,account_id:int,*,status:str,stored_count:int|None=None,new_count:int=0,updated_count:int=0,excluded_count:int=0,synced_at:str|None=None):
        now=synced_at or utc_now_iso();values={"member_sync_status":status,"last_member_sync_at":now,"last_member_new":new_count,"last_member_updated":updated_count,"last_member_excluded":excluded_count,"updated_at":now}
        if stored_count is not None:values["stored_member_count"]=stored_count
        assignments=",".join(f"{k}=?" for k in values);return self.db.execute(f"UPDATE group_accounts SET {assignments} WHERE group_id=? AND account_id=?",(*values.values(),group_id,account_id)).rowcount>0
