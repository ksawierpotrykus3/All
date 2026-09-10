# coding: utf-8
"""Dump surowego content entry dla checkout/build z HAR."""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
har = json.loads((BASE / "vinted.har").read_text(encoding="utf-8"))
entries = har["log"]["entries"]

for ent in entries:
    url = ent["request"]["url"]
    if "checkout/build" in url and ent["request"]["method"] == "POST":
        resp = ent["response"]
        print(json.dumps(resp.get("content", {}), ensure_ascii=False, indent=2)[:3000])
        print("--- response headers:")
        for h in resp.get("headers", []):
            print(f"  {h['name']}: {h['value'][:150]}")
        break
