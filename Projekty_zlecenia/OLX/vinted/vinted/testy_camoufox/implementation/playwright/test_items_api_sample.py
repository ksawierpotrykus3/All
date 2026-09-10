# coding: utf-8
"""Czy /api/v2/items/{id} kiedykolwiek zwraca 200? Proba na itemach z katalogu."""
import json
from pathlib import Path
from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

s = cr.Session()
cookies = json.loads((BASE_DIR / "cookies_profil.json").read_text(encoding="utf-8"))
for c in cookies:
    try:
        s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
    except Exception:
        pass
s.headers.update({
    "accept": "application/json,text/plain,*/*,image/webp",
    "accept-language": "pl,en-US;q=0.9,en;q=0.8,ru;q=0.7",
    "content-type": "application/json",
    "locale": "pl-PL",
    "origin": "https://www.vinted.pl",
    "referer": "https://www.vinted.pl/",
    "priority": "u=3",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
})
H = {"x-csrf-token": CSRF, "x-anon-id": ANON}
out = []

# itemy z katalogu testowego sprzedawcy (mymmelimyy89) - losowa probka
for it in [9822946391, 9813388084, 9823634785, 9803635610, 9796282823, 9816616926, 9807145386, 9669005364, 9816829405]:
    r = s.get(f"https://www.vinted.pl/api/v2/items/{it}", headers=H,
              impersonate=BrowserType.chrome146, timeout=30)
    out.append(f"item={it} -> http={r.status_code}")

# item aneta_003 (dostepny w przegladarce)
r = s.get("https://www.vinted.pl/api/v2/items/9807925466", headers=H,
          impersonate=BrowserType.chrome146, timeout=30)
out.append(f"item=9807925466 (aneta_003, dostepny) -> http={r.status_code}")

Path(BASE_DIR / "items_api_sample_out.txt").write_text("\n".join(out), encoding="utf-8")
print("\n".join(out))
