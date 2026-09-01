from __future__ import annotations
import csv
from pathlib import Path
from app.utils.formatters import utc_now_iso

class BlacklistService:
    def __init__(self,repository,member_repository=None,group_repository=None):self.repository=repository;self.member_repository=member_repository;self.group_repository=group_repository
    def get_page(self,page=1,page_size=100,search=None):return self.repository.get_page(page,page_size,search)
    def add_global(self,member_id:int,reason:str|None=None,kind:str="GLOBAL_BLACKLIST",notes:str|None=None):
        item=self.repository.add_global_exclusion(member_id,reason,notes,kind)
        if self.member_repository:
            self.member_repository.set_global_excluded(member_id,True)
            if kind=="DO_NOT_CONTACT":self.member_repository.set_eligibility(member_id,"DO_NOT_CONTACT")
            elif kind=="GLOBAL_BLACKLIST":self.member_repository.set_eligibility(member_id,"EXCLUDED")
        return item
    def add_global_by_telegram_id(self,telegram_user_id:int,reason:str|None=None,kind:str="GLOBAL_BLACKLIST",notes:str|None=None):
        if self.member_repository is None:raise ValueError("Member repository is unavailable.")
        member=self.member_repository.get_by_telegram_id(int(telegram_user_id))
        if not member:raise ValueError("Member not found in the local member pool.")
        return self.add_global(member.id,reason,kind,notes)
    def add_target(self,member_id:int,target_group_id:int,reason:str|None=None,notes:str|None=None):return self.repository._add(member_id,"TARGET_EXCLUSION",target_group_id,reason,notes)
    def remove(self,exclusion_id:int):
        row=self.repository.find_by_id(exclusion_id);result=self.repository.remove_exclusion(exclusion_id)
        if row and self.member_repository:
            member_id=int(row["member_id"]);self._recompute_global(member_id)
        return result
    def edit(self,exclusion_id:int,reason:str|None=None,notes:str|None=None):
        self.repository.update_fields(exclusion_id,{"reason":reason,"notes":notes,"updated_at":utc_now_iso()});return self.repository.find_by_id(exclusion_id)
    def remove_member_global(self,member_id:int):
        result=self.repository.remove_member_global(member_id)
        if self.member_repository:self._recompute_global(member_id)
        return result
    def is_excluded(self,member_id:int,target_group_id:int|None=None):return self.repository.is_globally_excluded(member_id) if target_group_id is None else self.repository.is_excluded_for_target(member_id,target_group_id)
    def targets(self):return self.group_repository.get_targets() if self.group_repository else []
    def _recompute_global(self,member_id:int):
        global_left=self.repository.is_globally_excluded(member_id);self.member_repository.set_global_excluded(member_id,global_left)
        if not global_left:
            member=self.member_repository.get_by_id(member_id)
            if member and member.eligibility_status in {"EXCLUDED","DO_NOT_CONTACT"}:self.member_repository.set_eligibility(member_id,"UNKNOWN")
    def import_csv(self,path):
        imported=skipped=errors=0;error_rows=[]
        with Path(path).open('r',encoding='utf-8-sig',newline='') as h:
            for line,row in enumerate(csv.DictReader(h),start=2):
                try:
                    tg=int(row.get('telegram_user_id') or '');kind=(row.get('exclusion_type') or 'GLOBAL_BLACKLIST').upper();target=(row.get('target_group_id') or '').strip()
                    member=self.member_repository.get_by_telegram_id(tg) if self.member_repository else None
                    if not member:raise ValueError("Member not found in the local member pool.")
                    if kind=="TARGET_EXCLUSION":
                        if not target:raise ValueError("target_group_id is required for TARGET_EXCLUSION.")
                        self.add_target(member.id,int(target),row.get('reason'),row.get('notes'))
                    else:self.add_global(member.id,row.get('reason'),kind,row.get('notes'))
                    imported+=1
                except ValueError as exc:skipped+=1;error_rows.append({'line':line,'error':str(exc)})
                except Exception as exc:errors+=1;error_rows.append({'line':line,'error':str(exc)})
        return {'imported':imported,'updated':0,'skipped':skipped,'errors':errors,'error_rows':error_rows}
    def export_csv(self,path,rows):
        with Path(path).open('w',encoding='utf-8-sig',newline='') as h:
            w=csv.writer(h);w.writerow(['telegram_user_id','username','exclusion_type','target_group_id','reason','created_at','notes'])
            for r in rows:
                d=dict(r);w.writerow([d.get('telegram_user_id',''),d.get('username',''),d.get('exclusion_type',''),d.get('target_group_id','') or '',d.get('reason','') or '',d.get('created_at',''),d.get('notes','') or ''])
