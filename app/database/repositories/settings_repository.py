from __future__ import annotations
from app.database.repositories.base_repository import BaseRepository
from app.utils.formatters import utc_now_iso
from app.utils.helpers import json_dumps_safe,json_loads_safe
class SettingsRepository(BaseRepository):
    table_name="app_settings"; id_column="key"; columns=("key","value","value_type","updated_at")
    def get(self,key:str,default=None):
        row=self.db.fetch_one("SELECT value,value_type FROM app_settings WHERE key=?",(key,))
        if not row: return default
        value=row["value"]; kind=str(row["value_type"] or "STRING").upper()
        if kind=="INTEGER":
            try:return int(value)
            except (TypeError,ValueError):return default
        if kind=="BOOLEAN": return str(value).lower() in {"1","true","yes","on"}
        if kind=="JSON": return json_loads_safe(value,default)
        return value
    def set(self,key:str,value):
        if isinstance(value,bool): kind="BOOLEAN"; stored="1" if value else "0"
        elif isinstance(value,int): kind="INTEGER"; stored=str(value)
        elif isinstance(value,(dict,list)): kind="JSON"; stored=json_dumps_safe(value)
        else: kind="STRING"; stored="" if value is None else str(value)
        self.db.execute("INSERT INTO app_settings(key,value,value_type,updated_at) VALUES(?,?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,value_type=excluded.value_type,updated_at=excluded.updated_at",(key,stored,kind,utc_now_iso())); return value
    def delete(self,key:str): return self.db.execute("DELETE FROM app_settings WHERE key=?",(key,)).rowcount>0
    def get_all(self): return {row["key"]:self.get(str(row["key"])) for row in self.db.fetch_all("SELECT key FROM app_settings ORDER BY key")}
