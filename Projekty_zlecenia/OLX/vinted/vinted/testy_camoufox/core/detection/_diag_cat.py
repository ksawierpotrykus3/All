# coding: utf-8
import json, sqlite3
from pathlib import Path
from curl_cffi import requests as cr

B = Path(__file__).resolve().parent
c = json.loads((B / "cookies_profil.json").read_text(encoding="utf-8"))
s = cr.Session()
for x in c:
    if x.get("name") == "datadome":
        continue
    try:
        s.cookies.set(x["name"], x["value"], domain=x.get("domain", ""), path=x.get("path", "/"))
    except Exception:
        pass
s.headers.update({
    "accept": "application/json",
    "locale": "pl-PL",
    "x-csrf-token": "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e",
    "x-anon-id": "98c6af5a-87da-45f2-9be5-24cf9345b003",
})
r = s.get("https://www.vinted.pl/api/v2/catalog/items"
          "?catalog_ids%5B%5D=44&price_to=50&order=newest_first&page=1&per_page=10&currency=PLN",
          impersonate="chrome136", timeout=30)
print("CATALOG", r.status_code, len(r.content))
try:
    print("items", len(r.json().get("items", [])))
except Exception as e:
    print("parse err", e, r.text[:200])

db = sqlite3.connect(str(B / "profil_firefox_135" / "cookies.sqlite"))  # kanoniczny profil
print("datadome w sqlite:", db.execute("SELECT count(*) FROM moz_cookies WHERE name='datadome'").fetchone()[0])
db.close()