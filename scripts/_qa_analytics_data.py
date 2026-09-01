"""Inspect DB data available for analytics redesign."""
import sqlite3
from pathlib import Path

DB = Path("data/tg_control.db")
con = sqlite3.connect(str(DB))
con.row_factory = sqlite3.Row
cur = con.cursor()

QUERIES = {
    "accounts_health": "SELECT health_status, COUNT(*) n FROM telegram_accounts GROUP BY health_status",
    "accounts_conn": "SELECT connection_status, COUNT(*) n FROM telegram_accounts GROUP BY connection_status",
    "groups_status": "SELECT status, COUNT(*) n FROM groups GROUP BY status",
    "groups_type": "SELECT group_type, COUNT(*) n FROM groups GROUP BY group_type",
    "groups_access": "SELECT access_type, COUNT(*) n FROM groups GROUP BY access_type",
    "members_elig": "SELECT eligibility_status, COUNT(*) n FROM members GROUP BY eligibility_status",
    "members_consent": "SELECT consent_status, COUNT(*) n FROM members GROUP BY consent_status",
    "members_bot": "SELECT is_bot, COUNT(*) n FROM members GROUP BY is_bot",
    "jobs_status": "SELECT status, COUNT(*) n FROM jobs GROUP BY status",
    "jobs_type": "SELECT job_type, COUNT(*) n FROM jobs GROUP BY job_type",
    "deliveries_status": "SELECT status, COUNT(*) n FROM campaign_deliveries GROUP BY status",
    "campaigns_status": "SELECT status, COUNT(*) n FROM campaigns GROUP BY status",
    "op_events_type": "SELECT event_type, COUNT(*) n FROM operation_events GROUP BY event_type",
    "op_events_sev": "SELECT severity, COUNT(*) n FROM operation_events GROUP BY severity",
    "alerts_sev": "SELECT severity, COUNT(*) n FROM alerts GROUP BY severity",
    "alerts_status": "SELECT status, COUNT(*) n FROM alerts GROUP BY status",
    "logs_level": "SELECT level, COUNT(*) n FROM logs GROUP BY level",
    "logs_category": "SELECT category, COUNT(*) n FROM logs GROUP BY category",
    "job_items_status": "SELECT status, COUNT(*) n FROM job_items GROUP BY status",
    "member_sync_runs": "SELECT status, COUNT(*) n FROM member_sync_runs GROUP BY status",
    "account_activity": "SELECT action_type, COUNT(*) n FROM account_activity GROUP BY action_type",
}

for name, q in QUERIES.items():
    try:
        rows = cur.execute(q).fetchall()
        print(f"{name}: {dict((r[0], r[1]) for r in rows)}")
    except Exception as e:
        print(f"{name}: ERROR {e}")

# date ranges
for name, q in {
    "jobs_by_day": "SELECT substr(created_at,1,10) d, COUNT(*) n FROM jobs GROUP BY d ORDER BY d DESC LIMIT 7",
    "op_by_day": "SELECT substr(created_at,1,10) d, COUNT(*) n FROM operation_events GROUP BY d ORDER BY d DESC LIMIT 7",
    "deliveries_by_day": "SELECT substr(created_at,1,10) d, COUNT(*) n FROM campaign_deliveries GROUP BY d ORDER BY d DESC LIMIT 7",
}.items():
    try:
        rows = cur.execute(q).fetchall()
        print(f"{name}: {[tuple(r) for r in rows]}")
    except Exception as e:
        print(f"{name}: ERROR {e}")

con.close()