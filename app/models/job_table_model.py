from __future__ import annotations

from datetime import datetime
from app.models.base_table_model import BaseTableModel
from app.utils.formatters import format_local_datetime

JOB_COLUMNS = ["Job ID", "Type", "Resource", "Account", "Group", "Campaign", "Progress", "Success", "Skipped", "Failed", "Created", "Started", "Duration", "Status"]


class JobTableModel(BaseTableModel):
    def __init__(self, rows, parent=None): super().__init__(rows, JOB_COLUMNS, parent)

    @staticmethod
    def _duration(job):
        if not job.started_at: return "—"
        try:
            start = datetime.fromisoformat(str(job.started_at).replace("Z", "+00:00"))
            end = datetime.fromisoformat(str(job.finished_at).replace("Z", "+00:00")) if job.finished_at else datetime.now(start.tzinfo)
            seconds = max(0, int((end - start).total_seconds())); return f"{seconds // 60}m {seconds % 60}s" if seconds >= 60 else f"{seconds}s"
        except Exception: return "—"

    def value_for_column(self, j, c):
        resource = f"{j.resource_type}:{j.resource_id}" if getattr(j, "resource_type", None) and getattr(j, "resource_id", None) else "—"
        return {
            "Job ID": j.id, "Type": j.job_type.replace("_", " ").title(), "Resource": resource,
            "Account": j.account_id or "—", "Group": j.group_id or "—", "Campaign": j.campaign_id or "—",
            "Progress": f"{j.progress}%", "Success": j.success_count, "Skipped": j.skipped_count, "Failed": j.failed_count,
            "Created": format_local_datetime(j.created_at), "Started": format_local_datetime(j.started_at),
            "Duration": self._duration(j), "Status": j.status.replace("_", " ").title(),
        }.get(c, "")
