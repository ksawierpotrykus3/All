# coding: utf-8
"""Wszystkie POST-y z body w HAR (poza consume) + odpowiedzi request_options."""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
har = json.loads((BASE / "vinted.har").read_text(encoding="utf-8"))
entries = har["log"]["entries"]

print("=== WSZYSTKIE POST-y (poza konsumem/telemetrią) ===")
for ent in entries:
    req = ent["request"]
    if req["method"] != "POST":
        continue
    url = req["url"]
    if any(x in url for x in ["consume", "analytics", "metrics", "pixel", "beacon", "config."]):
        continue
    body = req.get("postData", {}).get("text", "") if req.get("postData") else ""
    resp = ent["response"]
    print(f"[{resp['status']}] {url[:130]}")
    if body:
        print(f"    BODY: {body[:300]}")
