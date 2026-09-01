from __future__ import annotations

from app.database.repositories.base_repository import BaseRepository
from app.utils.formatters import utc_now_iso


class AlertRepository(BaseRepository):
    table_name = "alerts"
    columns = (
        "id", "severity", "alert_type", "title", "message", "account_id", "group_id",
        "campaign_id", "job_id", "is_read", "is_resolved", "created_at", "resolved_at",
        "dedupe_key", "source_type", "source_id", "first_seen_at", "last_seen_at",
        "occurrence_count", "requires_action", "action_type", "status",
    )

    def create_alert(self, severity: str, alert_type: str, title: str, message: str = "", **refs):
        now = utc_now_iso()
        dedupe_key = refs.get("dedupe_key")
        if dedupe_key:
            existing = self.db.fetch_one(
                "SELECT id,occurrence_count FROM alerts WHERE dedupe_key=? AND status IN ('OPEN','ACKNOWLEDGED') ORDER BY id DESC LIMIT 1",
                (dedupe_key,),
            )
            if existing:
                self.update_fields(int(existing["id"]), {
                    "severity": severity, "title": title, "message": message,
                    "last_seen_at": now, "occurrence_count": int(existing["occurrence_count"] or 1) + 1,
                    "requires_action": 1 if refs.get("requires_action") else 0,
                    "action_type": refs.get("action_type"), "is_read": 0, "status": "OPEN",
                })
                return int(existing["id"])
        return self.insert({
            "severity": severity, "alert_type": alert_type, "title": title, "message": message,
            "account_id": refs.get("account_id"), "group_id": refs.get("group_id"),
            "campaign_id": refs.get("campaign_id"), "job_id": refs.get("job_id"),
            "is_read": 0, "is_resolved": 0, "created_at": now, "resolved_at": None,
            "dedupe_key": dedupe_key, "source_type": refs.get("source_type"),
            "source_id": None if refs.get("source_id") is None else str(refs.get("source_id")),
            "first_seen_at": now, "last_seen_at": now, "occurrence_count": 1,
            "requires_action": 1 if refs.get("requires_action") else 0,
            "action_type": refs.get("action_type"), "status": refs.get("status", "OPEN"),
        })

    def mark_read(self, alert_id: int):
        return self.acknowledge(alert_id)

    def acknowledge(self, alert_id: int):
        return self.update_fields(alert_id, {"is_read": 1, "status": "ACKNOWLEDGED"})

    def resolve(self, alert_id: int):
        return self.update_fields(alert_id, {
            "is_read": 1, "is_resolved": 1, "status": "RESOLVED", "resolved_at": utc_now_iso(),
        })

    def mute(self, alert_id: int):
        return self.update_fields(alert_id, {"is_read": 1, "status": "MUTED"})

    def get_all(self, *, status: str | None = None, severity: str | None = None, limit: int = 1000):
        clauses: list[str] = []; params: list[object] = []
        if status and status != "ALL":
            if status == "ACTIVE":
                clauses.append("status IN ('OPEN','ACKNOWLEDGED')")
            else:
                clauses.append("status=?"); params.append(status)
        if severity and severity != "ALL": clauses.append("severity=?"); params.append(severity)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self.db.fetch_all(
            f"SELECT {', '.join(self.columns)} FROM alerts{where} ORDER BY COALESCE(last_seen_at,created_at) DESC LIMIT ?",
            (*params, limit),
        )
        return [dict(row) for row in rows]

    def get_by_id(self, alert_id: int):
        row = self.find_by_id(alert_id)
        return dict(row) if row else None

    def mark_all_read(self):
        now = utc_now_iso()
        self.db.execute(
            "UPDATE alerts SET is_read=1,status=CASE WHEN status='OPEN' THEN 'ACKNOWLEDGED' ELSE status END,last_seen_at=COALESCE(last_seen_at,?) WHERE is_read=0",
            (now,),
        )
        return True

    def clear_resolved(self):
        self.db.execute("DELETE FROM alerts WHERE status='RESOLVED' OR is_resolved=1")
        return True

    def count_open(self, severity: str | None = None) -> int:
        params: tuple[object, ...] = ()
        extra = ""
        if severity:
            extra = " AND severity=?"; params = (severity,)
        row = self.db.fetch_one(
            f"SELECT COUNT(*) AS n FROM alerts WHERE status IN ('OPEN','ACKNOWLEDGED') AND is_resolved=0{extra}", params,
        )
        return int(row["n"] if row else 0)

    def cleanup_resolved_before(self, cutoff_iso: str) -> int:
        cursor = self.db.execute(
            "DELETE FROM alerts WHERE (status='RESOLVED' OR is_resolved=1) AND COALESCE(resolved_at,last_seen_at,created_at) < ?",
            (cutoff_iso,),
        )
        return int(cursor.rowcount)
