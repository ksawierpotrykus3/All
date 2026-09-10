# coding: utf-8
import sqlite3
from pathlib import Path

db_path = Path(__file__).resolve().parent / "profil_firefox_135" / "cookies.sqlite"
db = sqlite3.connect(str(db_path))
rows = db.execute(
    "SELECT name, host, length(value) FROM moz_cookies WHERE host LIKE '%vinted%' ORDER BY name"
).fetchall()
db.close()

print("=== vinted cookies w profil_firefox_135/cookies.sqlite ===")
for name, host, ln in rows:
    print(f"{name:30s} {host:30s} len={ln}")
dd = [r for r in rows if r[0] == "datadome"]
print("datadome obecne:", bool(dd))