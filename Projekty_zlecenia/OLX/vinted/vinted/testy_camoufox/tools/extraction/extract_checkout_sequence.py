# coding: utf-8
"""Wyciąga z HAR pełne nagłówki i odpowiedzi requestów checkout/build -> PUT -> payment."""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
har = json.loads((BASE / "vinted.har").read_text(encoding="utf-8"))
entries = har["log"]["entries"]

targets = [
    "/purchases/checkout/build",
    "/purchases/eWjYk_Oxxq3qOpWC4gee4/checkout",
    "/checkout/payment",
]

out = []
for ent in entries:
    url = ent["request"]["url"]
    method = ent["request"]["method"]
    if "purchases" in url and any(t in url for t in targets):
        req = ent["request"]
        resp = ent["response"]
        rec = {
            "method": method,
            "url": url,
            "request_headers": [{"name": h["name"], "value": h["value"]} for h in req["headers"]],
            "post_body": req.get("postData", {}).get("text", "") if req.get("postData") else "",
            "status": resp["status"],
            "response_body": resp.get("content", {}).get("text", "") if resp.get("content") else "",
            "cookies_sent": [{"name": c["name"], "value": c["value"]} for c in req.get("cookies", [])],
            "cookies_received": [{"name": c["name"], "value": c["value"]} for c in resp.get("cookies", [])],
        }
        out.append(rec)

(BASE / "checkout_sequence_from_har.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

for i, rec in enumerate(out):
    print(f"\n===== [{i}] {rec['method']} {rec['url']} -> {rec['status']}")
    for h in rec["request_headers"]:
        print(f"  REQ  {h['name']}: {h['value'][:120]}")
    if rec["post_body"]:
        print(f"  BODY {rec['post_body'][:600]}")
