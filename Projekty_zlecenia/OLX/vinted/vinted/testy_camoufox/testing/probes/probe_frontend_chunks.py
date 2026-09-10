# coding: utf-8
"""Pobiera kluczowe chunki JS z marketplace-web-assets i szuka flow tworzenia transakcji/buy."""
import json
import re
from pathlib import Path
from curl_cffi import requests as cr
from curl_cffi import BrowserType

BASE_DIR = Path(__file__).resolve().parent
CHUNKS = [
    "https://marketplace-web-assets.vinted.com/_next/static/chunks/0jvs9.75d7av~.js",
    "https://marketplace-web-assets.vinted.com/_next/static/chunks/0ja4_ft81ixl2.js",
    "https://marketplace-web-assets.vinted.com/_next/static/chunks/0bkkkxcvmlbsf.js",
]

s = cr.Session()
s.headers.update({
    "accept": "*/*",
    "accept-language": "pl,en-US;q=0.9,en;q=0.8",
    "referer": "https://www.vinted.pl/",
})

PATTERNS = [
    r"purchases/checkout/build",
    r"checkout/build",
    r"/transactions",
    r"buy_now|buy-now|buyNow",
    r"request_options",
    r"order_type",
    r"escrow",
    r"create.*transaction",
]

for url in CHUNKS:
    try:
        r = s.get(url, impersonate=BrowserType.chrome146, timeout=30)
        js = r.text
        fn = url.split("/")[-1][:50]
        print(f"\n########## {fn} ({len(js)}B, status={r.status_code}) ##########")
        for pat in PATTERNS:
            hits = list(re.finditer(pat, js))
            if hits:
                print(f"  ### {pat}: {len(hits)}")
                for m in hits[:3]:
                    s0 = max(0, m.start() - 120)
                    print("     ..." + js[s0:m.end() + 120].replace("\n", " ")[:260] + "...")
    except Exception as e:  # noqa: BLE001
        print(f"\n########## {url} ERROR: {e}")
