from __future__ import annotations

from dataclasses import asdict
from app.license.license_models import LicenseDevice, LicenseState
from app.utils.formatters import utc_now_iso
from app.utils.helpers import json_dumps_safe, json_loads_safe

STATE_COLUMNS = ("id","plan","status","license_key_masked","license_reference","expires_at","activated_at","last_validated_at","offline_grace_until","device_id","device_name","server_license_id","cached_license_payload","created_at","updated_at")

class LicenseRepository:
    def __init__(self, database): self.db=database
    def get_state(self) -> LicenseState | None:
        row=self.db.fetch_one(f"SELECT {', '.join(STATE_COLUMNS)} FROM license_state WHERE id=1")
        if not row:return None
        data=dict(row);data["cached_license_payload"]=json_loads_safe(data.get("cached_license_payload"),None)
        return LicenseState(**data)
    def save_state(self,state:LicenseState)->LicenseState:
        now=utc_now_iso();existing=self.get_state();created=state.created_at or (existing.created_at if existing else None) or now
        values=asdict(state);values["id"]=1;values["created_at"]=created;values["updated_at"]=now;values["cached_license_payload"]=json_dumps_safe(state.cached_license_payload) if state.cached_license_payload is not None else None
        cols=STATE_COLUMNS;placeholders=','.join('?' for _ in cols);updates=','.join(f"{c}=excluded.{c}" for c in cols if c!='id')
        self.db.execute(f"INSERT INTO license_state({', '.join(cols)}) VALUES({placeholders}) ON CONFLICT(id) DO UPDATE SET {updates}",tuple(values[c] for c in cols))
        return self.get_state()
    def clear_state(self): self.db.execute("DELETE FROM license_state WHERE id=1")
    def add_history(self,event_type,old_plan=None,new_plan=None,old_status=None,new_status=None,message=None):
        return int(self.db.execute("INSERT INTO license_history(event_type,old_plan,new_plan,old_status,new_status,message,created_at) VALUES(?,?,?,?,?,?,?)",(event_type,old_plan,new_plan,old_status,new_status,message,utc_now_iso())).lastrowid)
    def history(self,limit=100): return [dict(r) for r in self.db.fetch_all("SELECT * FROM license_history ORDER BY id DESC LIMIT ?",(int(limit),))]
    def replace_devices(self,devices:list[LicenseDevice]):
        now=utc_now_iso()
        with self.db.transaction():
            self.db.execute("DELETE FROM license_devices")
            if devices:self.db.execute_many("INSERT INTO license_devices(server_device_id,device_id,device_name,platform,is_current,is_active,activated_at,last_seen_at,last_synced_at) VALUES(?,?,?,?,?,?,?,?,?)",[(d.server_device_id,d.device_id,d.device_name,d.platform,int(d.is_current),int(d.is_active),d.activated_at,d.last_seen_at,now) for d in devices])
    def get_devices(self):
        return [LicenseDevice(server_device_id=r['server_device_id'],device_id=r['device_id'],device_name=r['device_name'],platform=r['platform'],is_current=bool(r['is_current']),is_active=bool(r['is_active']),activated_at=r['activated_at'],last_seen_at=r['last_seen_at'],last_synced_at=r['last_synced_at']) for r in self.db.fetch_all("SELECT * FROM license_devices ORDER BY is_current DESC,is_active DESC,id")]
    def active_device_count(self):
        row=self.db.fetch_one("SELECT COUNT(*) count FROM license_devices WHERE is_active=1");return int(row['count'] if row else 0)
