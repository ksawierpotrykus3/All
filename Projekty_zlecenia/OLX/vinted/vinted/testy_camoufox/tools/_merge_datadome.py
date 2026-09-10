# coding: utf-8
"""_merge_datadome.py — wstrzykuje cookie `datadome` z cookies.sqlite profilu
do cookies_profil.json (eksport uzywany przez testy curl_cffi / NewContext).

Powod niespojnosci: reset_datadome_cookie.py usunal datadome, a publiczne strony
w headless nie odtworzylу go -> eksport byl BEZ tokenu DataDome -> build/payment 403.
Po tym, jak strona itemu w build_probe ustawila datadome w profilu, doklejamy go tu.

UWAGA: cookies.sqlite trzyma expiry w ms (10^13); Playwright/curl_cffi oczekuja
sekund -> konwersja.
"""
import json
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB = BASE_DIR.parent / "implementation" / "browser-profiles" / "profil_firefox_135" / "cookies.sqlite"  # kanoniczny profil
OUT = BASE_DIR / "cookies_profil.json"

conn = sqlite3.connect(str(DB))
rows = conn.execute(
    "SELECT value, host, expiry FROM moz_cookies WHERE name='datadome' ORDER BY expiry DESC"
).fetchall()
conn.close()

if not rows:
    print("BRAK datadome w cookies.sqlite")
    raise SystemExit(1)

value, host, expiry = rows[0]
exp_s = int(expiry / 1000.0) if expiry > 10**12 else int(expiry)

cookies = json.loads(OUT.read_text(encoding="utf-8"))
cookies = [c for c in cookies if c.get("name") != "datadome"]
cookies.append({
    "name": "datadome",
    "value": value,
    "domain": host,
    "path": "/",
    "expires": exp_s,
    "httpOnly": True,
    "secure": True,
    "sameSite": "Lax",
})
OUT.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"OK: datadome wstrzykniety do {OUT} ({value[:30]}... exp={exp_s})")
