# coding: utf-8
"""Wyciagnij entry 702 z HAR - odpowiedz nearby_pickup_points."""
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
with open(BASE_DIR / "vinted.har", "r", encoding="utf-8", errors="ignore") as f:
    har = json.load(f)

entries = har["log"]["entries"]
e = entries[702]
req = e["request"]
print("URL:", req["url"])
print("METHOD:", req["method"])
body = e.get("response", {}).get("content", {}).get("text", "")
print("RESP LEN:", len(body))
print(body[:4000])
