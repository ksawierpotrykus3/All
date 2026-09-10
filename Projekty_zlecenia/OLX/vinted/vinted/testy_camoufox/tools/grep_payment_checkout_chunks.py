# coding: utf-8
"""Wyciaga modul platnosci z chunkow checkoutu."""
import re
from pathlib import Path

files = ["131~8x_i~m-aw.js", "0yhhqgn4m5t2_.js", "0m6z-r2_~i3np.js", "0qq55ycmhfrl9.js"]
d = Path(__file__).resolve().parent / "chunks_har"

for fn in files:
    p = d / fn
    if not p.exists():
        print(f"### {fn}: BRAK")
        continue
    js = p.read_text(encoding="utf-8", errors="replace")
    print(f"\n########## {fn} (len={len(js)}) ##########")
    for pat in [r"checkout/payment", r"initiatePayment", r"payment/options", r"pay_in_method", r"paymentOptions"]:
        for m in list(re.finditer(pat, js))[:4]:
            s0 = max(0, m.start() - 150)
            print(f"\n--- {pat} @ {m.start()} ---")
            print(js[s0:m.end() + 250].replace("\n", " ")[:400])
