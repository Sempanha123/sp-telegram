"""Quick DB + screenshot analysis for avatar verification."""
import sqlite3
import sys
from pathlib import Path

from PIL import Image

DB = Path("data/tg_control.db")


def check_db():
    con = sqlite3.connect(str(DB))
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    print("tables:", tables)
    for t in ("accounts", "groups", "members"):
        if t in tables:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            print(t, "count=", cur.fetchone()[0])
    con.close()


AVATAR_BG = {
    (219, 234, 254), (237, 233, 254), (209, 250, 229), (254, 243, 199),
    (254, 226, 226), (207, 250, 254), (252, 231, 247), (224, 231, 255),
}


def check_screens():
    d = Path("screenshots/qa_light4")
    for name in ("accounts_light.png", "groups_light.png", "members_light.png"):
        p = d / name
        if not p.exists():
            print(name, "MISSING")
            continue
        im = Image.open(str(p)).convert("RGB")
        w, h = im.size
        px = im.load()
        found = {}
        for y in range(0, h, 2):
            for x in range(0, min(w, 300), 2):
                rgb = px[x, y]
                if rgb in AVATAR_BG:
                    found[rgb] = found.get(rgb, 0) + 1
        print(name, im.size, "avatar-pastel:", dict(sorted(found.items(), key=lambda kv: -kv[1])[:5]))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "db":
        check_db()
    else:
        check_screens()