from __future__ import annotations

import os, platform, uuid
from pathlib import Path
from app.constants import APP_VERSION
from app.security.secure_storage import KeyringSecureStorage, SecureStorage, SecureStorageError

class DeviceManager:
    STORAGE_KEY="license_device_id"
    def __init__(self,storage:SecureStorage|None=None,fallback_path:str|Path|None=None):
        self.storage=storage or KeyringSecureStorage();self.fallback_path=Path(fallback_path) if fallback_path else None
    def get_device_id(self)->str:
        value=None
        try:value=self.storage.get_secret(self.STORAGE_KEY)
        except SecureStorageError: value=None
        if not value and self.fallback_path and self.fallback_path.is_file():
            try:value=self.fallback_path.read_text(encoding='utf-8').strip()
            except OSError:value=None
        if not value:
            value=str(uuid.uuid4())
            stored=False
            try:self.storage.set_secret(self.STORAGE_KEY,value);stored=True
            except SecureStorageError:stored=False
            if not stored and self.fallback_path:
                self.fallback_path.parent.mkdir(parents=True,exist_ok=True);self.fallback_path.write_text(value,encoding='utf-8')
                try:os.chmod(self.fallback_path,0o600)
                except OSError:pass
        return value
    def mask_device_id(self,device_id:str|None=None)->str:
        value=(device_id or self.get_device_id()).replace('-','')
        return f"****-****-{value[-4:].upper()}"
    def metadata(self,device_name:str|None=None)->dict:
        return {"device_id":self.get_device_id(),"device_name":(device_name or platform.node() or 'This Device')[:80],"platform":f"{platform.system()} {platform.release()}".strip(),"application_version":APP_VERSION}
