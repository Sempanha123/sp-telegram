from __future__ import annotations
from pathlib import Path
class SettingsService:
    SENSITIVE_KEYS={"api_id","api_hash","otp","2fa_password","password"}
    def __init__(self,repository,database): self.repository=repository; self.database=database
    def get(self,key,default=None): return self.repository.get(key,default)
    def get_all(self): return self.repository.get_all()
    def save(self,values:dict):
        for key,value in values.items():
            if key.lower() in self.SENSITIVE_KEYS: continue
            self.repository.set(key,value)
        return True
    def reset(self):
        for key in list(self.repository.get_all()): self.repository.delete(key)
    def backup(self,path): return self.database.backup_to(path)
    def restore(self,path,safety_backup_dir): return self.database.restore_from(path,safety_backup_dir=safety_backup_dir)
