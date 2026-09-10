# coding: utf-8
"""Wyciaga z HAR wszystkie URL-e chunkow JS (_next/static/chunks) z czesci item page."""
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
HAR = BASE_DIR / "vinted.har"

with open(HAR, encoding="utf-8") as f:
    har = json.load(f)

entries = har["log"]["entries"]
print(f"Razem entries: {len(entries)}")

chunks = {}
for i, e in enumerate(entries):
    url = e["request"]["url"]
    if "/_next/static/chunks/" in url and url.endswith(".js"):
        # usun query string i hash wersji
        base = url.split("?")[0]
        chunks[base] = {"entry_idx": i, "url": url}

print(f"\nUnikalne chunki JS: {len(chunks)}")
for base, info in sorted(chunks.items(), key=lambda kv: kv[1]["entry_idx"]):
    print(f"  [{info['entry_idx']:>4}] {base}")
