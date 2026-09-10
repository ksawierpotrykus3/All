# coding: utf-8
"""Znajdz w HAR requesty dotyczace punktow odbioru / shipping."""
import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
har_path = BASE_DIR / "vinted.har"

# Wczytaj tylko 'entries' w streamie? HAR ma 48MB - czytaj JSON w pelni (juz dzialalo).
with open(har_path, "r", encoding="utf-8", errors="ignore") as f:
    har = json.load(f)

entries = har["log"]["entries"]
print(f"Entries: {len(entries)}")

pats = re.compile(r"(shipping_point|shipping_points|pickup_point|pickup_points|points|rate_uuid|carrier)", re.I)
for i, e in enumerate(entries):
    req = e["request"]
    method = req["method"]
    url = req["url"]
    if method != "GET":
        continue
    if "vinted" not in url:
        continue
    if pats.search(url):
        print(f"[{i}] {method} {url[:220]}")
