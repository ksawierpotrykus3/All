# coding: utf-8
"""Szuka definicji initiateSingleCheckoutPayment / updateSingleCheckoutPaymentFailure."""
import re
from pathlib import Path

d = Path(__file__).resolve().parent / "chunks_har"
for fn in sorted(d.glob("*.js")):
    js = fn.read_text(encoding="utf-8", errors="replace")
    for pat in [r"initiateSingleCheckoutPayment", r"updateSingleCheckoutPaymentFailure", r"refreshPurchase"]:
        for m in list(re.finditer(pat, js)):
            s0 = max(0, m.start() - 200)
            print(f"[{fn.name}] {pat} @ {m.start()}")
            print("   ", js[s0:m.end() + 400].replace("\n", " ")[:600])
            print()
