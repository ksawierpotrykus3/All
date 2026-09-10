# coding: utf-8
"""Wyciąga pełny request+response offers/request_options i okolicę indeksu build z HAR."""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
har = json.loads((BASE / "vinted.har").read_text(encoding="utf-8"))
entries = har["log"]["entries"]

for i, ent in enumerate(entries):
    url = ent["request"]["url"]
    m = ent["request"]["method"]
    if "request_options" in url:
        req = ent["request"]
        resp = ent["response"]
        body = req.get("postData", {}).get("text", "") if req.get("postData") else ""
        print(f"INDEX {i} [{m}] {url} -> {resp['status']}")
        print(f"REQ BODY: {body}")
        print(f"RESP BODY[{len(resp.get('content',{}).get('text',''))}]: "
              f"{resp.get('content',{}).get('text','')[:2500]}")
        print(f"RESP content-encoding: {dict((h['name'],h['value']) for h in resp.get('headers',[]) if h['name']=='content-encoding')}")
        print("=" * 80)

# Kontekst 15 entries przed build
build_idx = None
for i, ent in enumerate(entries):
    if "checkout/build" in ent["request"]["url"] and ent["request"]["method"] == "POST":
        build_idx = i
        break
print(f"\n=== KONTEKST {build_idx-15}..{build_idx} ===")
for ent in entries[max(0, build_idx - 15):build_idx]:
    url = ent["request"]["url"]
    m = ent["request"]["method"]
    body = ent["request"].get("postData", {}).get("text", "") if ent["request"].get("postData") else ""
    if "api.vinted" in url or "www.vinted.pl/api" in url or "images" not in url:
        print(f"[{m}] {url[:150]}  status={ent['response']['status']}")
        if body:
            print(f"    BODY: {body[:200]}")
