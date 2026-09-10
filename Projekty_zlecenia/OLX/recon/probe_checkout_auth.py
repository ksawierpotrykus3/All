"""Pobierz stronę checkoutu z Bearer tokenem i wyciągnij __NEXT_DATA__ + ścieżki API."""
import base64
import json
import re
from pathlib import Path

from curl_cffi import requests

BASE = Path(__file__).resolve().parent.parent
COOKIES_PATH = BASE / "dane" / "cookies.txt"


def read_token():
    for line in COOKIES_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = line.split("\t")
        if len(p) >= 7 and p[5] == "access_token":
            return p[6]
    raise SystemExit("brak access_token")


def main():
    token = read_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "text/html,application/xhtml+xml",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    }
    url = "https://www.olx.pl/delivery/checkout/1084508890/"
    r = requests.get(url, headers=headers, impersonate="chrome124", timeout=20)
    html = r.text

    print(f"status={r.status_code} len={len(html)}")

    # zapisz surowy html
    (BASE / "dane" / "checkout_auth_page.html").write_text(html, encoding="utf-8")

    # 1. __NEXT_DATA__
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
    next_data = None
    if m:
        try:
            next_data = json.loads(m.group(1))
            (BASE / "dane" / "checkout_next_data.json").write_text(
                json.dumps(next_data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print("[+] __NEXT_DATA__ zapisany")
        except Exception as e:
            print("[!] __NEXT_DATA__ parse error:", e)

    # 2. buildId
    bid = re.search(r'"buildId"\s*:\s*"([^"]+)"', html)
    print("buildId:", bid.group(1) if bid else "brak")

    # 3. ścieżki API
    api_paths = set()
    for pat in [r'https?://[^"\'\s<>]+', r'"/api/[^"\']+', r"'/api/[^']+", r'"/[a-z-]+/checkout/[^"\']+', r'"/delivery/[^"\']+']:
        for x in re.findall(pat, html):
            x = x.strip('"\'')
            if any(k in x.lower() for k in ("api", "delivery", "checkout", "rock", "payu", "payment", "order", "buy")):
                api_paths.add(x)

    out = {
        "status": r.status_code,
        "len": len(html),
        "buildId": bid.group(1) if bid else None,
        "api_paths": sorted(api_paths)[:200],
    }
    (BASE / "dane" / "checkout_auth_paths.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\n[+] Ścieżki API:")
    for p in sorted(api_paths)[:80]:
        print("   ", p)


if __name__ == "__main__":
    main()