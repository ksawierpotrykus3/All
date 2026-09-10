# coding: utf-8
"""Szuka we wszystkich wyciągach JS: jak wywoływany jest checkout/build, skąd transaction_id."""
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
files = ["checkout_payload_extract.txt", "transaction_type_extract.txt", "extract_checkout_output.txt"]

for fn in files:
    p = BASE / fn
    if not p.exists():
        continue
    text = p.read_text(encoding="utf-8")
    print(f"\n########## {fn} (len={len(text)}) ##########")
    for pat in [r"navigateToCheckout", r"request_options", r"buy_now|buy-now|buy now", r"/transactions", r"checkout/build", r"initiateSingleCheckout", r"Kup teraz|buy-now|buyNow"]:
        for m in re.finditer(pat, text, re.IGNORECASE):
            start = max(0, m.start() - 250)
            end = min(len(text), m.end() + 250)
            frag = text[start:end].replace("\n", " ")
            print(f"--- [{pat}] @{m.start()}:")
            print(f"    ...{frag}...")
