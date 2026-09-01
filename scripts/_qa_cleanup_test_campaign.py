"""Remove QA runtime test campaigns from the database."""
import sqlite3
from pathlib import Path

DB = Path("data/tg_control.db")
con = sqlite3.connect(str(DB))
cur = con.cursor()
rows = cur.execute(
    "SELECT id, name, status FROM campaigns WHERE name LIKE 'QA Runtime%'"
).fetchall()
print("Test campaigns found:", rows)
for cid, name, status in rows:
    cur.execute("DELETE FROM campaign_messages WHERE campaign_id=?", (cid,))
    cur.execute("DELETE FROM campaign_targets WHERE campaign_id=?", (cid,))
    cur.execute("DELETE FROM campaign_deliveries WHERE campaign_id=?", (cid,))
    cur.execute("DELETE FROM campaigns WHERE id=?", (cid,))
con.commit()
print("Cleaned up. Remaining campaigns:", cur.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0])
con.close()