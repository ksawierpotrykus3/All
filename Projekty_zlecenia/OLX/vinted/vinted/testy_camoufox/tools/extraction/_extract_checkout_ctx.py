# coding: utf-8
"""Wyciąga kontekst wokół kluczowych funkcji checkout/payment z minifikowanych chunków."""
import re
from pathlib import Path

BASE = Path(r"f:\PROJEKTY\vinted\vinted\testy_camoufox\chunks_har")
TERMS = ["initiatePayment", "payment_options", "checksum", "updateSingleCheckoutData",
         "shipping_pickup_details", "nearby_pickup_points", "pickupPointCode", "pointCode"]

for f in BASE.glob("*.js"):
    txt = f.read_text(encoding="utf-8", errors="ignore")
    for term in TERMS:
        idx = txt.find(term)
        if idx != -1:
            start = max(0, idx - 250)
            end = min(len(txt), idx + 450)
            snippet = txt[start:end]
            print(f"\n===== {f.name} :: {term} =====")
            print(snippet)
            break  # jeden snippet per plik wystarczy