# coding: utf-8
"""Wypisuje response body requestów checkout z HAR (build, PUT checkout, payment)."""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
har = json.loads((BASE / "vinted.har").read_text(encoding="utf-8"))
entries = har["log"]["entries"]

for ent in entries:
    url = ent["request"]["url"]
    method = ent["request"]["method"]
    if "purchases" in url and "checkout" in url:
        resp = ent["response"]
        body = resp.get("content", {}).get("text", "") if resp.get("content") else ""
        # też cookies response
        ck = [c["name"] for c in resp.get("cookies", [])]
        print(f"\n===== {method} {url} -> {resp['status']}  resp_cookies={ck}")
        print(f"BODY[{len(body)}]: {body[:2000]}")
