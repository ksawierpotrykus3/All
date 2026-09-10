# coding: utf-8
"""Szuka w HAR: wszystkie wystąpienia 9807925466 i 21872241924 w URL i body requestów."""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
har = json.loads((BASE / "vinted.har").read_text(encoding="utf-8"))
entries = har["log"]["entries"]

IDS = ["9807925466", "21872241924", "35270544124"]  # item, transaction, offer

print("=== URL-e zawierające item/transaction/offer id ===")
for i, ent in enumerate(entries):
    url = ent["request"]["url"]
    for idd in IDS:
        if idd in url:
            print(f"[{i}] {ent['request']['method']} {url[:170]} -> {ent['response']['status']}  (id: {idd})")
            break

print("\n=== Body requestów zawierające te id ===")
for i, ent in enumerate(entries):
    req = ent["request"]
    body = req.get("postData", {}).get("text", "") if req.get("postData") else ""
    for idd in IDS:
        if idd in body:
            print(f"[{i}] {req['method']} {req['url'][:130]} -> {ent['response']['status']}")
            print(f"     BODY: {body[:250]}")
            break
