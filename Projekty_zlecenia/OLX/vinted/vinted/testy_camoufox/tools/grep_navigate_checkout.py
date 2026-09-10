# coding: utf-8
"""Szuka wywolan navigateToCheckout i typu transaction we wszystkich chunkach."""
import re
from pathlib import Path

d = Path(__file__).resolve().parent / "chunks_har"
pats = [
    r"useNavigateToCheckout",
    r"navigateToCheckout\s*\(",
    r"order_type\s*:\s*['\"]transaction",
    r"checkout_type\s*:\s*['\"]transaction",
    r"type\s*:\s*['\"]transaction",
    r"transaction_id\s*:",
]
for fn in sorted(d.glob("*.js")):
    js = fn.read_text(encoding="utf-8", errors="replace")
    for pat in pats:
        for m in list(re.finditer(pat, js)):
            s0 = max(0, m.start() - 150)
            print(f"[{fn.name}] {pat} @ {m.start()}")
            print("   ", js[s0:m.end() + 180].replace("\n", " ")[:360])
            print()
