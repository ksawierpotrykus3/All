# coding: utf-8
"""Pobiera WSZYSTKIE chunki JS z HAR i greppuje flow buy/transaction."""
import json
import re
import time
from pathlib import Path

from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent
HAR = BASE_DIR / "vinted.har"
OUT = BASE_DIR / "chunks_har"

with open(HAR, encoding="utf-8") as f:
    har = json.load(f)

chunks = []
seen = set()
for i, e in enumerate(har["log"]["entries"]):
    url = e["request"]["url"]
    if "/_next/static/chunks/" in url and url.endswith(".js"):
        base = url.split("?")[0]
        if base not in seen:
            seen.add(base)
            chunks.append((i, base))

print(f"Chunkow do pobrania: {len(chunks)}")
OUT.mkdir(exist_ok=True)

s = cr.Session()
s.headers.update({
    "accept": "*/*",
    "accept-language": "pl,en-US;q=0.9,en;q=0.8",
    "referer": "https://www.vinted.pl/",
})

ok = 0
for idx, url in chunks:
    fn = OUT / (url.rsplit("/", 1)[-1].split("?")[0])
    if fn.exists() and fn.stat().st_size > 1000:
        ok += 1
        continue
    try:
        r = s.get(url, impersonate=BrowserType.chrome146, timeout=30)
        fn.write_bytes(r.content)
        ok += 1
        if ok % 20 == 0:
            print(f"  ...{ok}/{len(chunks)}")
    except Exception as ex:  # noqa: BLE001
        print(f"  ERROR {url}: {ex}")
    time.sleep(0.15)

print(f"Pobrano: {ok}/{len(chunks)}")

# Grep po wszystkich chunkach
PATTERNS = [
    (r"buy_now|buyNow|buy-now|BuyNow", "buy"),
    (r"/api/v\d+/(transactions|items/|purchases)", "api_endpoint"),
    (r"create.*(transaction|purchase)|transaction.*create", "create_txn"),
    (r"order_type", "order_type"),
    (r"escrow", "escrow"),
    (r"checkout/build", "checkout_build"),
    (r"navigateToCheckout|useNavigateToCheckout", "navigate"),
]

print("\n========== WYNIKI GREP ==========")
for fn in sorted(OUT.glob("*.js")):
    js = fn.read_text(encoding="utf-8", errors="replace")
    for pat, label in PATTERNS:
        for m in list(re.finditer(pat, js))[:2]:
            s0 = max(0, m.start() - 80)
            frag = js[s0:m.end() + 100].replace("\n", " ")
            print(f"\n[{label}] {fn.name} @ {m.start()}")
            print("   ..." + frag[:200] + "...")
