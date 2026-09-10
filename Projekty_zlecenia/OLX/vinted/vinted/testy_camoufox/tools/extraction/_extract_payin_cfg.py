# coding: utf-8
"""Wyciąga kontekst konfiguracji checkout / metod płatności."""
from pathlib import Path

BASE = Path(r"f:\PROJEKTY\vinted\vinted\testy_camoufox\chunks_har")
TERMS = ["configurations/checkout", "getCheckoutConfigurations", "pay_in_methods",
         "payInMethods", "payment_methods", "checkout_configuration", "pay_in"]

for f in BASE.glob("*.js"):
    txt = f.read_text(encoding="utf-8", errors="ignore")
    for term in TERMS:
        idx = txt.find(term)
        if idx != -1:
            start = max(0, idx - 300)
            end = min(len(txt), idx + 600)
            print(f"\n===== {f.name} :: {term} =====")
            print(txt[start:end])
            break