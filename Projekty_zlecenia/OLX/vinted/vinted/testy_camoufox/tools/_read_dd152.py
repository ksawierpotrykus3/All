# coding: utf-8
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "implementation" / "browser-profiles"
for name in ("profil_firefox_135",):  # kanoniczny profil (stare profil_firefox usunięte)
    db_path = BASE / name / "cookies.sqlite"
    if not db_path.exists():
        print(f"{name}: brak cookies.sqlite")
        continue
    db = sqlite3.connect(str(db_path))
    rows = db.execute(
        "SELECT name, host, value, expiry FROM moz_cookies WHERE name='datadome'"
    ).fetchall()
    db.close()
    print(f"=== {name} ===")
    for n, host, val, exp in rows:
        print(f"host={host} expiry={exp} value={val[:80]}...")
    if not rows:
        print("(brak datadome)")