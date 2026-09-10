# coding: utf-8
"""Wyciąga kontekst pay_in_method / payment_methods z chunków."""
from pathlib import Path

BASE = Path(r"f:\PROJEKTY\vinted\vinted\testy_camoufox\chunks_har")
TERMS = ["pay_in_method_id", "payInMethodId", "pay_in_methods", "available_payment_methods",
         "payment_methods", "blikCode", "pay_in"]

for f in BASE.glob("*.js"):
    txt = f.read_text(encoding="utf-8", errors="ignore")
    for term in TERMS:
        idx = txt.find(term)
        if idx != -1:
            start = max(0, idx - 250)
            end = min(len(txt), idx + 450)
            print(f"\n===== {f.name} :: {term} =====")
            print(txt[start:end])
            break