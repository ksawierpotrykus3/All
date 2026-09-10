# coding: utf-8
"""Wyciąga kontekst tworzenia transakcji i buy-now z chunków."""
import re
from pathlib import Path

BASE = Path(r"f:\PROJEKTY\vinted\vinted\testy_camoufox\chunks_har")
TERMS = ["item-buy-button", "ItemPageBuyButton", "useCreateConversation",
         "createTransaction", "request_options", "initiateSingleCheckout"]

for f in BASE.glob("*.js"):
    txt = f.read_text(encoding="utf-8", errors="ignore")
    for term in TERMS:
        idx = txt.find(term)
        if idx != -1:
            start = max(0, idx - 300)
            end = min(len(txt), idx + 500)
            print(f"\n===== {f.name} :: {term} =====")
            print(txt[start:end])