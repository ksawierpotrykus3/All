# coding: utf-8
"""Wyciaga z HAR entry konwersacji/transakcji (POST /conversations, /messaging/main/inquiries)."""
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
HAR = BASE_DIR / "vinted.har"

with open(HAR, encoding="utf-8") as f:
    har = json.load(f)

entries = har["log"]["entries"]

# Szukamy POST do /conversations lub inquiries
for i, e in enumerate(entries):
    req = e["request"]
    url = req["url"]
    method = req["method"]
    if method == "POST" and ("conversations" in url or "inquiries" in url):
        print("=" * 90)
        print(f"ENTRY {i} | {method} {url}")
        # Headers
        hdrs = {h["name"]: h["value"] for h in req["headers"]}
        for k in ["x-csrf-token", "x-anon-id", "x-incognia-request-token", "content-type"]:
            if k in hdrs:
                print(f"  HDR {k} = {hdrs[k][:120]}")
        # Post body
        if req.get("postData", {}).get("text"):
            print(f"  BODY: {req['postData']['text'][:500]}")
        else:
            # params
            for p in req.get("postData", {}).get("params", []):
                print(f"  PARAM {p['name']} = {str(p.get('value',''))[:300]}")
        # Response
        resp = e.get("response", {})
        print(f"  STATUS: {resp.get('status')}")
        content = resp.get("content", {})
        txt = content.get("text", "")
        if txt:
            print(f"  RESPONSE ({content.get('size')}B): {txt[:2000]}")
        else:
            print(f"  RESPONSE: no text (mime={content.get('mimeType')}, size={content.get('size')})")
        # response headers
        for h in resp.get("headers", []):
            if h["name"].lower() in ("x-incognia-request-token", "location", "x-request-id"):
                print(f"  RSP_HDR {h['name']} = {h['value'][:150]}")
