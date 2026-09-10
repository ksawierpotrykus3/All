"""F5e2: Dump wyników inspekcji do JSON (bez stdout).
"""
from __future__ import annotations
import json
from pathlib import Path

HAR = Path(r"f:\PROJEKTY\vinted\vinted\testy_camoufox\vinted.har")
OUT = Path(r"f:\PROJEKTY\vinted\vinted\testy_camoufox\wynik_spike_F5e_full_inspect.json")

data = json.loads(HAR.read_text(encoding="utf-8", errors="replace"))
entries = data["log"]["entries"]

icg_indices = [100, 101, 103, 258, 259, 261, 487, 488, 490, 641, 642, 643]
out = {"inspected": []}

for idx in icg_indices:
    e = entries[idx]
    req = e.get("request", {})
    resp = e.get("response", {})
    cont = resp.get("content", {})

    item = {
        "idx": idx,
        "method": req.get("method"),
        "url": req.get("url"),
        "status": resp.get("status"),
        "req_headers": [{"name": h["name"], "value": h["value"]} for h in req.get("headers", [])],
        "req_body": req.get("postData", {}).get("text", "")[:1000],
        "resp_headers": [{"name": h["name"], "value": h["value"]} for h in resp.get("headers", [])],
        "resp_body_text": (cont.get("text") or "")[:1000],
        "resp_size": cont.get("size"),
        "resp_transferSize": cont.get("_transferSize"),
        "resp_mime": cont.get("mimeType"),
        "resp_encoding": cont.get("encoding"),
        "queryString": req.get("queryString", []),
    }
    out["inspected"].append(item)

OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"OK: zapisano {len(out['inspected'])} entries do {OUT}")
print(f"Rozmiar: {OUT.stat().st_size:,} B")
