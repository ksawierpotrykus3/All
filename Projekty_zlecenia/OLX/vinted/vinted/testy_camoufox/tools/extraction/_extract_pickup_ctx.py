# coding: utf-8
"""Wyciąga kontekst wokół sugerowanego punktu odbioru z chunków."""
import re
from pathlib import Path

BASE = Path(r"f:\PROJEKTY\vinted\vinted\testy_camoufox\chunks_har")
TERMS = ["suggestedShippingPointCode", "suggested_shipping_point_code",
         "pickupPointCode", "pickup_point_code", "preselect", "defaultPickupPoint"]

for f in BASE.glob("*.js"):
    txt = f.read_text(encoding="utf-8", errors="ignore")
    for term in TERMS:
        idx = txt.find(term)
        if idx != -1:
            start = max(0, idx - 200)
            end = min(len(txt), idx + 300)
            print(f"\n===== {f.name} :: {term} =====")
            print(txt[start:end])
            break