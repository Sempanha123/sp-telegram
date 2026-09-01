import sqlite3

conn = sqlite3.connect("data/tg_control.db")
cur = conn.cursor()
print("=== app_settings (connect/auto) ===")
for row in cur.execute("SELECT key, value FROM app_settings WHERE key LIKE '%connect%' OR key LIKE '%auto%'"):
    print(row)
print("=== telegram_accounts ===")
cur.execute(
    "SELECT id, first_name, username, telegram_user_id, connection_status, "
    "authorization_status, is_enabled, session_path FROM telegram_accounts"
)
for row in cur.fetchall():
    print(row)
print("=== related history for account 2 ===")
for table, column in (
    ("account_activity", "account_id"),
    ("account_restrictions", "account_id"),
    ("group_accounts", "account_id"),
    ("jobs", "account_id"),
    ("campaign_targets", "account_id"),
    ("target_invite_links", "account_id"),
):
    try:
        row = cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} = 2").fetchone()
        print(f"{table}: {row[0]}")
    except Exception as exc:
        print(f"{table}: ERROR {exc}")
conn.close()