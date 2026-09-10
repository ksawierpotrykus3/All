# coding: utf-8
"""Sprawdza, czy chunki JS w HAR mają zdekodowaną treść (content.text)."""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
har = json.loads((BASE / "vinted.har").read_text(encoding="utf-8"))
entries = har["log"]["entries"]

# chunk JS z item page (306, 471-478)
for i in [306, 471, 472, 473, 475, 476, 477, 478]:
    ent = entries[i]
    url = ent["request"]["url"]
    resp = ent["response"]
    content = resp.get("content", {})
    has_text = bool(content.get("text"))
    enc = content.get("encoding")
    size = content.get("size")
    comp = content.get("compression")
    print(f"[{i}] {url.split('/')[-1][:50]} text={has_text} enc={enc} size={size} comp={comp}")
