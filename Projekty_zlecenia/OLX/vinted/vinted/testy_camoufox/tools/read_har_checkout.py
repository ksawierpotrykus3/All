# coding: utf-8
"""Wyciaga z vinted.har pelne requesty checkout/build i checkout/payment
(headery + body + response) i zapisuje do read_har_out.json + wypisuje podsumowanie."""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
HAR = BASE / "vinted.har"
OUT = BASE / "read_har_out.json"

har = json.loads(HAR.read_text(encoding="utf-8"))
entries = har["log"]["entries"]

wanted = ["checkout/build", "checkout/payment", "conversations"]
hits = []
for e in entries:
    url = e["request"]["url"]
    if any(w in url for w in wanted):
        req = e["request"]
        res = e["response"]
        hits.append({
            "url": url,
            "method": req["method"],
            "time_ms": round(e.get("time", 0), 1),
            "req_headers": {h["name"]: h["value"] for h in req["headers"]},
            "post_data": (req.get("postData") or {}).get("text", ""),
            "resp_status": res["status"],
            "resp_body": (res.get("content") or {}).get("text", "")[:2000],
        })

OUT.write_text(json.dumps(hits, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Znaleziono {len(hits)} pasujacych entry w HAR\n")
for h in hits:
    print(f"--- {h['method']} {h['url']} [{h['time_ms']}ms -> {h['resp_status']}]")
    # wazne headery
    for k in ("user-agent", "x-incognia-request-token", "x-csrf-token", "x-anon-id", "referer",
              "content-type", "accept", "sec-ch-ua", "sec-ch-ua-mobile", "sec-ch-ua-platform",
              "origin", "sec-fetch-site", "x-checkout-token", "x-signature"):
        if k in h["req_headers"]:
            v = h["req_headers"][k]
            print(f"  {k}: {v[:160]}")
    if h["post_data"]:
        print(f"  BODY: {h['post_data'][:500]}")
    print()
