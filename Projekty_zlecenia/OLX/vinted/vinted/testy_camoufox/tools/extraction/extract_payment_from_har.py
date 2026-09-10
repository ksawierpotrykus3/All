# coding: utf-8
"""Wyciaga z HAR request payment + szuka GET transakcji/statusu 220."""
import json
from pathlib import Path

har = json.loads(Path("vinted.har").read_text(encoding="utf-8"))
entries = har["log"]["entries"]

print("### Requesty payment / transakcje / statusy ###")
for i, e in enumerate(entries):
    req = e["request"]
    url = req["url"]
    method = req["method"]
    if ("payment" in url or "transactions" in url or "reservation" in url) and method != "OPTIONS":
        ts = e.get("startedDateTime", "")[11:19]
        print(f"\n[{ts}] ENTRY {i} | {method} {url[:160]}")
        hdrs = {h["name"]: h["value"] for h in req["headers"]}
        if "x-incognia-request-token" in hdrs:
            print(f"  x-incognia-request-token: {hdrs['x-incognia-request-token'][:60]}...")
        pd = req.get("postData", {})
        if pd.get("text"):
            print(f"  BODY: {pd['text'][:1200]}")
        elif pd.get("params"):
            print(f"  PARAMS: {pd['params']}")
        print(f"  STATUS: {e.get('response', {}).get('status')}")
        resp_txt = e.get("response", {}).get("content", {}).get("text", "")
        if resp_txt and resp_txt.strip():
            print(f"  RESP: {resp_txt[:600]}")
