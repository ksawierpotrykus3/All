# coding: utf-8
"""Wylistuj z HAR endpointy API dot. items/catalog/wardrobe (metoda + url)."""
import json
import re

har = json.load(open("vinted.har", encoding="utf-8"))
pat = re.compile(r"(items|catalog|wardrobe)")
seen = set()
for entry in har.get("log", {}).get("entries", []):
    req = entry.get("request", {})
    url = req.get("url", "")
    if re.search(r"/api/", url) and pat.search(url):
        key = (req.get("method", ""), re.sub(r"https://www\.vinted\.pl", "", url))
        if key not in seen:
            seen.add(key)
            print(f"{key[0]} {key[1]}")
