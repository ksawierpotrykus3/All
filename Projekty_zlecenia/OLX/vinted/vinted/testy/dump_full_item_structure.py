import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from curl_cffi import requests as creq
import json

s = creq.Session(impersonate="chrome124")
r0 = s.get("https://www.vinted.pl/", timeout=15)
token = s.cookies.get("access_token_web")

headers = {
    "Authorization": f"Bearer {token}",
    "X-Anonymous-Id": s.cookies.get("anon_id", ""),
    "Accept": "application/json, text/plain, */*",
}

r = s.get("https://www.vinted.pl/api/v2/catalog/items?order=newest_first&per_page=1", headers=headers)
if r.status_code == 200:
    item = r.json()["items"][0]
    print("=== PEŁNA STRUKTURA OFERTY ZWRACANA PRZEZ /api/v2/catalog/items ===")
    print(json.dumps(item, indent=2, ensure_ascii=False))
