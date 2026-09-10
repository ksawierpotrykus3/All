# coding: utf-8
"""Wyciąga requesty 284..489 z HAR (item page -> build) - tylko vinted api, bez szumu."""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
har = json.loads((BASE / "vinted.har").read_text(encoding="utf-8"))
entries = har["log"]["entries"]

SKIP = ["google", "doubleclick", "adsystem", "gstatic", "maps.", "analytics", "braze",
        "sentry", "qwtag", "confiant", "id5", "fastclick", "pubads", "gtg/", "ccm/",
        "applepay", "font", "cdn.cookielaw", "amazon", "przelewy24", "adyen", "img.", "images"]
for i in range(284, 490):
    ent = entries[i]
    req = ent["request"]
    url = req["url"]
    if any(x in url for x in SKIP):
        continue
    m = req["method"]
    body = req.get("postData", {}).get("text", "") if req.get("postData") else ""
    print(f"[{i}] {m} {url[:150]} -> {ent['response']['status']}")
    if body:
        print(f"     BODY: {body[:200]}")
