from __future__ import annotations
from dataclasses import asdict
from typing import Any
from app.database.repositories.base_repository import BaseRepository
from app.models.entities import TelegramGroup
from app.utils.formatters import utc_now_iso

COLS=("id","telegram_group_id","title","username","group_type","access_type","access_state","member_count","description","is_verified","is_scam","is_fake","is_forum","is_broadcast","is_megagroup","is_gigagroup","linked_chat_id","photo_cache_path","is_source","is_target","is_managed","status","last_sync_at","last_error_code","last_error_message","last_error_at","created_at","updated_at")

class GroupRepository(BaseRepository):
    table_name="groups"; columns=COLS
    def create(self,item:TelegramGroup):
        now=utc_now_iso(); data=asdict(item); data.pop("id",None)
        for k in list(data):
            if k not in COLS:data.pop(k,None)
        data["created_at"]=item.created_at or now;data["updated_at"]=now
        item.id=self.insert(data);return self.get_by_id(item.id)
    def update(self,item:TelegramGroup):
        if item.id is None:raise ValueError("Group id is required.")
        data=asdict(item);data["updated_at"]=utc_now_iso();self.update_fields(item.id,data);return self.get_by_id(item.id)
    def get_by_id(self,id:int):
        return TelegramGroup.from_row(self.db.fetch_one(self._detail_sql("g.id=?"),(id,)))
    def get_by_telegram_id(self,value:int):
        return TelegramGroup.from_row(self.db.fetch_one(self._detail_sql("g.telegram_group_id=?"),(value,)))
    def get_by_username(self,value:str):
        return TelegramGroup.from_row(self.db.fetch_one(self._detail_sql("LOWER(g.username)=LOWER(?)"),(value.lstrip("@"),)))
    def _detail_sql(self,where:str):
        fields=", ".join("g."+c for c in COLS)
        return f"""SELECT {fields}, COALESCE(ga.role,'UNKNOWN') role, COALESCE(a.first_name,a.username,'') account_name,
        ga.account_id primary_account_id, COALESCE(ga.access_state,'UNKNOWN') mapping_access_state,
        ga.can_post can_post, ga.can_invite can_invite, ga.can_manage can_manage
        FROM groups g LEFT JOIN group_accounts ga ON ga.group_id=g.id AND ga.is_primary=1
        LEFT JOIN telegram_accounts a ON a.id=ga.account_id WHERE {where}"""
    def _list(self,where:str="",params=()):
        clause=f" WHERE {where}" if where else ""; fields=", ".join("g."+c for c in COLS)
        rows=self.db.fetch_all(f"""SELECT {fields}, COALESCE(ga.role,'UNKNOWN') role, COALESCE(a.first_name,a.username,'') account_name,
        ga.account_id primary_account_id, COALESCE(ga.access_state,'UNKNOWN') mapping_access_state,ga.can_post,ga.can_invite,ga.can_manage
        FROM groups g LEFT JOIN group_accounts ga ON ga.group_id=g.id AND ga.is_primary=1
        LEFT JOIN telegram_accounts a ON a.id=ga.account_id{clause} ORDER BY g.id DESC""",params)
        return [TelegramGroup.from_row(r) for r in rows]
    def get_all(self):return self._list()
    def get_sources(self):return self._list("g.is_source=1")
    def get_targets(self):return self._list("g.is_target=1")
    def get_managed(self):return self._list("g.is_managed=1")
    def search(self,query:str):
        term=f"%{query.strip()}%";return self._list("g.title LIKE ? OR g.username LIKE ? OR CAST(g.telegram_group_id AS TEXT) LIKE ?",(term,term,term))
    def get_page(self,page:int,page_size:int,search:str|None=None,group_type:str|None=None,access:str|None=None,flag:str|None=None,status:str|None=None,role:str|None=None,classification:str|None=None,account_id:int|None=None):
        where=[];params:list[Any]=[]
        if search:term=f"%{search.strip()}%";where.append("(g.title LIKE ? OR g.username LIKE ? OR CAST(g.telegram_group_id AS TEXT) LIKE ?)");params += [term,term,term]
        if group_type and group_type.upper()!="ALL":where.append("g.group_type=?");params.append(group_type.upper().replace(" ","_"))
        if access and access.upper()!="ALL":
            val=access.upper().replace(" ","_")
            if val=="PUBLIC":where.append("g.access_type='PUBLIC'")
            elif val=="PRIVATE":where.append("g.access_type='PRIVATE'")
            else:where.append("g.access_state=?");params.append(val)
        effective=classification or flag
        if effective and effective.lower() in {"source","target","managed"}:where.append(f"g.is_{effective.lower()}=1")
        if status and status.upper()!="ALL":where.append("g.status=?");params.append(status.upper().replace(" ","_"))
        if role and role.upper()!="ALL":where.append("ga.role=?");params.append(role.upper())
        if account_id:where.append("EXISTS(SELECT 1 FROM group_accounts gx WHERE gx.group_id=g.id AND gx.account_id=?)");params.append(account_id)
        clause=" WHERE "+" AND ".join(where) if where else ""
        count=self.db.fetch_one(f"SELECT COUNT(DISTINCT g.id) count FROM groups g LEFT JOIN group_accounts ga ON ga.group_id=g.id AND ga.is_primary=1{clause}",tuple(params))
        off=(max(1,page)-1)*page_size;fields=", ".join("g."+c for c in COLS)
        rows=self.db.fetch_all(f"""SELECT {fields}, COALESCE(ga.role,'UNKNOWN') role,COALESCE(a.first_name,a.username,'') account_name,
        ga.account_id primary_account_id,COALESCE(ga.access_state,'UNKNOWN') mapping_access_state,ga.can_post,ga.can_invite,ga.can_manage
        FROM groups g LEFT JOIN group_accounts ga ON ga.group_id=g.id AND ga.is_primary=1 LEFT JOIN telegram_accounts a ON a.id=ga.account_id
        {clause} ORDER BY g.id DESC LIMIT ? OFFSET ?""",(*params,page_size,off))
        return [TelegramGroup.from_row(r) for r in rows],int(count["count"] if count else 0)
    def upsert_resolved_group(self,resolved,*,is_source=None,is_target=None,is_managed=None):
        existing=self.get_by_telegram_id(int(resolved.telegram_group_id)) if int(resolved.telegram_group_id or 0)>0 else None
        if existing:item=existing
        else:item=TelegramGroup(telegram_group_id=int(resolved.telegram_group_id),title=resolved.title)
        item.title=resolved.title;item.username=resolved.username;item.group_type=resolved.type;item.access_type=resolved.access_type;item.access_state=resolved.access_state
        item.member_count=int(resolved.member_count or 0);item.description=resolved.description;item.is_verified=int(resolved.is_verified);item.is_scam=int(resolved.is_scam);item.is_fake=int(resolved.is_fake);item.is_forum=int(resolved.is_forum);item.is_broadcast=int(resolved.is_broadcast);item.is_megagroup=int(resolved.is_megagroup);item.is_gigagroup=int(resolved.is_gigagroup);item.linked_chat_id=resolved.linked_chat_id
        item.status="READY";item.last_sync_at=utc_now_iso();item.last_error_code=None;item.last_error_message=None;item.last_error_at=None
        if is_source is not None:item.is_source=int(bool(is_source))
        if is_target is not None:item.is_target=int(bool(is_target))
        if is_managed is not None:item.is_managed=int(bool(is_managed))
        return self.update(item) if existing else self.create(item)
    def update_metadata(self,id:int,values:dict):
        allowed={k:v for k,v in values.items() if k in COLS and k not in {"id","is_source","is_target","is_managed","created_at"}};allowed["updated_at"]=utc_now_iso();return self.update_fields(id,allowed)
    def update_access_state(self,id:int,state:str):return self.update_fields(id,{"access_state":state,"updated_at":utc_now_iso()})
    def update_sync_status(self,id:int,status:str,error_code=None,error_message=None):return self.update_fields(id,{"status":status,"last_error_code":error_code,"last_error_message":error_message,"last_error_at":utc_now_iso() if error_code else None,"updated_at":utc_now_iso()})
    def set_source(self,id:int,value:bool):return self.update_fields(id,{"is_source":int(value),"updated_at":utc_now_iso()})
    def set_target(self,id:int,value:bool):return self.update_fields(id,{"is_target":int(value),"updated_at":utc_now_iso()})
    def set_managed(self,id:int,value:bool):return self.update_fields(id,{"is_managed":int(value),"updated_at":utc_now_iso()})
    def update_member_count(self,id:int,count:int):return self.update_fields(id,{"member_count":max(0,count),"updated_at":utc_now_iso()})
    def update_sync_time(self,id:int):return self.update_fields(id,{"last_sync_at":utc_now_iso(),"updated_at":utc_now_iso()})
    def count_all(self):return self.count()
    def count_sources(self):return self.count("is_source=1")
    def count_targets(self):return self.count("is_target=1")
    def count_managed(self):return self.count("is_managed=1")
    def count_public(self):return self.count("access_type='PUBLIC'")
    def count_private(self):return self.count("access_type='PRIVATE'")
    def count_by_type(self,value:str):return self.count("group_type=?",(value,))
    def count_by_status(self,value:str):return self.count("status=?",(value,))
    def count_errors(self):return self.count("status IN ('ERROR','ACCESS_DENIED','UNAVAILABLE')")
