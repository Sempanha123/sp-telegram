from __future__ import annotations
from app.models.base_table_model import BaseTableModel
from app.utils.formatters import format_local_datetime

LOG_COLUMNS = ["Time", "Level", "Category", "Account", "Group", "Campaign", "Job", "Action", "Message"]


class LogTableModel(BaseTableModel):
    def __init__(self, rows, parent=None): super().__init__(rows, LOG_COLUMNS, parent)
    def value_for_column(self, l, c):
        return {
            "Time": format_local_datetime(l.created_at), "Level": l.level.title(), "Category": l.category.title(),
            "Account": l.account_id or "—", "Group": l.group_id or "—", "Campaign": getattr(l, "campaign_id", None) or "—",
            "Job": getattr(l, "job_id", None) or "—", "Action": l.action or "—", "Message": l.message,
        }.get(c, "")
