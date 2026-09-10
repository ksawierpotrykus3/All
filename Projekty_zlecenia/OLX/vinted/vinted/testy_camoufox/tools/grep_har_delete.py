# coding: utf-8
"""Wszystkie requesty DELETE + 'cancel'/'delete' w HAR."""
import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
with open(BASE_DIR / "vinted.har", "r", encoding="utf-8", errors="ignore") as f:
    har = json.load(f)

entries = har["log"]["entries"]
out = []
for i, e in enumerate(entries):
    req = e["request"]
    method = req["method"]
    url = req["url"]
    if method in ("DELETE", "PUT") or re.search(r"cancel|delete|abandon|issue", url, re.I):
        out.append(f"[{i}] {method} {url[:200]}")
        pb = req.get("postData", {}).get("text", "")
        if pb:
            out.append(f"    BODY: {pb[:300]}")

Path(BASE_DIR / "har_delete_cancel_out.txt").write_text("\n".join(out), encoding="utf-8")
print("OK")
