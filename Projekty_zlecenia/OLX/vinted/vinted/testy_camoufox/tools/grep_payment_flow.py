# coding: utf-8
"""Szuka w chunkach flow płatnosci: initiatePayment, checkout/payment, reservation."""
import re
from pathlib import Path

d = Path(__file__).resolve().parent / "chunks_har"
pats = [
    r"checkout/payment",
    r"initiatePayment",
    r"payment/options",
    r"payment_options",
    r"reserved|reservation",
]
for fn in sorted(d.glob("*.js")):
    js = fn.read_text(encoding="utf-8", errors="replace")
    for pat in pats:
        for m in list(re.finditer(pat, js)):
            s0 = max(0, m.start() - 120)
            frag = js[s0:m.end() + 200].replace("\n", " ")
            print(f"[{fn.name}] {pat} @ {m.start()}")
            print("   ", frag[:320])
            print()
