# coding: utf-8
"""Pobiera live stronę itemu przez curl_cffi i szuka w HTML śladów tworzenia transakcji/buy flow."""
import json
import re
from pathlib import Path
from curl_cffi import requests as cr
from curl_cffi import BrowserType

BASE_DIR = Path(__file__).resolve().parent
ITEM_ID = 9807925466

s = cr.Session()
cookies = json.loads((BASE_DIR / "cookies_profil.json").read_text(encoding="utf-8"))
for c in cookies:
    try:
        s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
    except Exception:  # noqa: BLE001
        pass
s.headers.update({
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "pl,en-US;q=0.9,en;q=0.8",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
})

r = s.get(f"https://www.vinted.pl/items/{ITEM_ID}-genesis-krypton-700",
          impersonate=BrowserType.chrome146, timeout=30)
print(f"status={r.status_code}, len={len(r.text)}")
html = r.text

# Szukamy transakcji / buy / escrow w HTML
for pat in [r"transaction[^\"']{0,40}", r"buy_now[^\"']{0,40}", r"buy-now[^\"']{0,40}",
            r"escrow[^\"']{0,40}", r"order_id[^\"']{0,40}", r"purchase[^\"']{0,40}",
            r"21872241924", r"35270544124"]:
    hits = re.findall(pat, html, re.IGNORECASE)
    if hits:
        print(f"\n### {pat}: {len(hits)} hitów")
        for h in list(dict.fromkeys(hits))[:8]:
            print(f"   {h}")

# Zapisz HTML do pliku dla głębszej analizy
(BASE_DIR / "item_page_live.html").write_text(html, encoding="utf-8")
print(f"\nZapisano HTML: {len(html)} znaków")
