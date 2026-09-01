from __future__ import annotations
import shutil
from pathlib import Path

class TelegramMediaService:
    def __init__(self,project_root:Path):self.root=Path(project_root)/'data'/'media'/'campaigns';self.root.mkdir(parents=True,exist_ok=True)
    def validate(self,path:str|None)->tuple[bool,str|None]:
        if not path:return False,'Media file is required.'
        p=Path(path)
        if not p.is_file():return False,'Media file is missing or unreadable.'
        try:
            with p.open('rb') as fh:fh.read(1)
        except OSError:return False,'Media file is not readable.'
        return True,None
    def adopt(self,campaign_id:int,path:str)->str:
        ok,error=self.validate(path)
        if not ok:raise ValueError(error)
        src=Path(path);folder=self.root/str(campaign_id);folder.mkdir(parents=True,exist_ok=True)
        safe=''.join(c if c.isalnum() or c in '._- ' else '_' for c in src.name).strip() or 'media.bin';dst=folder/safe
        if src.resolve()!=dst.resolve():shutil.copy2(src,dst)
        return str(dst)
