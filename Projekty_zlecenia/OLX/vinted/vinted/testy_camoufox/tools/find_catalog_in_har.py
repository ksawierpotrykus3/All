# coding: utf-8
"""Szuka w HAR requestow catalog/search oraz item page."""
import json
from pathlib import Path

har = json.loads(Path("vinted.har").read_text(encoding="utf-8"))
for i, e in enumerate(har["log"]["entries"]):
    url = e["request"]["url"]
    m = e["request"]["method"]
    if any(k in url for k in ("catalog", "search", "items/")):
        print(f"{i} | {m} {url[:220]}")
