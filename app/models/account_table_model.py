from __future__ import annotations

from pathlib import Path

from app.models.base_table_model import BaseTableModel
from app.utils.formatters import format_local_datetime, mask_phone


ACCOUNT_COLUMNS = [
    "Select", "ID", "Account", "Telegram ID", "Username", "Phone", "Premium",
    "Operational Status", "Current Job", "Connection", "Authorization", "Health", "Session", "Last Active",
    "Last Connected", "Last Health Check", "Last Error", "Tags",
]


class AccountTableModel(BaseTableModel):
    def __init__(self, rows, parent=None):
        super().__init__(rows, ACCOUNT_COLUMNS, parent)
        self.privacy_mode = False
        self.mask_telegram_ids = False
        self.mask_usernames = False
        self.mask_phone_numbers = True

    def set_privacy_mode(self, enabled: bool):
        self.privacy_mode = bool(enabled); self.layoutChanged.emit()

    def set_display_preferences(self, *, mask_telegram_ids=None, mask_usernames=None, mask_phone_numbers=None):
        if mask_telegram_ids is not None: self.mask_telegram_ids = bool(mask_telegram_ids)
        if mask_usernames is not None: self.mask_usernames = bool(mask_usernames)
        if mask_phone_numbers is not None: self.mask_phone_numbers = bool(mask_phone_numbers)
        self.layoutChanged.emit()

    def value_for_column(self, a, c):
        if c == "Session":
            if getattr(a, "is_demo", 0):
                return "Demo"
            if not a.session_path:
                return "Not configured"
            return "Available" if Path(a.session_path).is_file() else "Missing"
        mapping = {
            "Select": "",
            "ID": a.id,
            "Account": a.first_name or a.username or f"Account {a.id}",
            "Telegram ID": ("••••••" if (self.privacy_mode or self.mask_telegram_ids) and a.telegram_user_id else a.telegram_user_id),
            "Username": ("@••••••" if (self.privacy_mode or self.mask_usernames) and a.username else (f"@{a.username}" if a.username else "—")),
            "Phone": ("••••••" if (self.privacy_mode or self.mask_phone_numbers) and a.phone else mask_phone(a.phone)),
            "Premium": bool(a.is_premium),
            "Operational Status": str(getattr(a, "operational_status", "IDLE")).replace("_", " ").title(),
            "Current Job": getattr(a, "current_job", "Idle"),
            "Connection": str(a.connection_status).replace("_", " ").title(),
            "Authorization": str(getattr(a, "authorization_status", "UNKNOWN")).replace("_", " ").title(),
            "Health": str(a.health_status).replace("_", " ").title(),
            "Last Active": format_local_datetime(a.last_active_at),
            "Last Connected": format_local_datetime(a.last_connected_at),
            "Last Health Check": format_local_datetime(a.last_health_check_at),
            "Last Error": a.last_error_message or "—",
            "Tags": getattr(a, "tags", "") or "—",
        }
        return mapping.get(c, "")
