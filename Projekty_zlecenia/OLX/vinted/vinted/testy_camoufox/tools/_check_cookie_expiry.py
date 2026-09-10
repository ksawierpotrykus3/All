"""Sprawdzenie daty wygasniecia kluczowych cookies Vinted."""
import sqlite3
import time
from pathlib import Path

DB = Path(r"F:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135\cookies.sqlite")  # kanoniczny profil
conn = sqlite3.connect(str(DB))
cur = conn.cursor()

# Kluczowe cookies sesyjne
KEY_COOKIES = ("access_token_web", "refresh_token_web", "_vinted_fr_session",
               "anon_id", "datadome", "cf_clearance", "__cf_bm")

print(f"Now (epoch): {int(time.time())}\n")
print(f"{'cookie':30s} | {'host':25s} | exp_epoch  | exp_date")
print("-" * 100)
rows = cur.execute(
    "SELECT name, host, expiry FROM moz_cookies "
    "WHERE name IN (" + ",".join("?" * len(KEY_COOKIES)) + ") "
    "ORDER BY name",
    KEY_COOKIES,
).fetchall()
for r in rows:
    name, host, exp = r
    if exp and exp > 0:
        # Firefox przechowuje expiry w SEKUNDACH (Unix timestamp) dla cookies.sqlite
        # ale czasem w ms (np. > 10^12)
        from datetime import datetime, timezone
        exp_s = exp / 1000.0 if exp > 10**12 else exp
        try:
            dt = datetime.fromtimestamp(exp_s, tz=timezone.utc)
        except Exception:
            dt = "?"
        days = (exp_s - int(time.time())) / 86400
        print(f"{name:30s} | {host:25s} | {int(exp_s):10d} | {dt}  ({days:+.1f}d)")
    else:
        print(f"{name:30s} | {host:25s} | {'session':10s} | (session)")
conn.close()
