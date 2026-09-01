from __future__ import annotations
import csv
from pathlib import Path
from app.security.sensitive_data_filter import SensitiveDataFilter


class LogService:
    def __init__(self, repository): self.repository = repository; self.filter = SensitiveDataFilter()
    def add(self, level: str, category: str, message: str, **kwargs): return self.repository.add_log(level, category, message, **kwargs)
    def get_page(self, page=1, page_size=100, search=None, level=None, category=None, **filters): return self.repository.get_page(page, page_size, search, level, category, **filters)
    def import_csv(self, path: str | Path):
        imported=skipped=errors=0; error_rows=[]
        with Path(path).open("r",encoding="utf-8-sig",newline="") as handle:
            for line,row in enumerate(csv.DictReader(handle),start=2):
                try:self.add((row.get("level") or "INFO").upper(),(row.get("category") or "SYSTEM").upper(),self.filter.redact(row.get("message") or ""),action=row.get("action") or None);imported+=1
                except ValueError as exc:skipped+=1;error_rows.append({"line":line,"error":str(exc)})
                except Exception as exc:errors+=1;error_rows.append({"line":line,"error":str(exc)})
        return {"imported":imported,"updated":0,"skipped":skipped,"errors":errors,"error_rows":error_rows}
    def export_filtered_csv(self, path: str | Path, *, search=None, level=None, category=None, **filters):
        """Stream the complete current database filter without loading large log history into UI memory."""
        with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["created_at", "level", "category", "account_id", "group_id", "campaign_id", "job_id", "action", "message"])
            page = 1
            page_size = 500
            while True:
                items, total = self.repository.get_page(page, page_size, search, level, category, **filters)
                for x in items:
                    writer.writerow([x.created_at, x.level, x.category, x.account_id or "", x.group_id or "", x.campaign_id or "", x.job_id or "", x.action or "", self.filter.redact(x.message)])
                if not items or page * page_size >= total:
                    break
                page += 1

    def export_csv(self,path:str|Path,items):
        with Path(path).open("w",encoding="utf-8-sig",newline="") as handle:
            writer=csv.writer(handle); writer.writerow(["created_at","level","category","account_id","group_id","campaign_id","job_id","action","message"])
            for x in items: writer.writerow([x.created_at,x.level,x.category,x.account_id or "",x.group_id or "",x.campaign_id or "",x.job_id or "",x.action or "",self.filter.redact(x.message)])
