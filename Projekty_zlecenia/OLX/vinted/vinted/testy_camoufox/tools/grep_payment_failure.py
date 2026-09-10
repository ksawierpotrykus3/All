# coding: utf-8
"""Wyciagnij definicje payment/failure z chunkow."""
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent / "chunks_har"
out = []
for f in sorted(BASE.glob("*.js")):
    txt = f.read_text(encoding="utf-8", errors="ignore")
    if "payment/failure" in txt:
        for m in re.finditer(r"payment/failure", txt):
            s = max(0, m.start() - 700)
            e = min(len(txt), m.end() + 700)
            out.append(f"===== {f.name} =====")
            out.append(txt[s:e])
            out.append("")
# tez 'payment/continue' i 'payment' GET
for f in sorted(BASE.glob("*.js")):
    txt = f.read_text(encoding="utf-8", errors="ignore")
    if "updateSingleCheckoutPaymentFailure" in txt or "cancelPayment" in txt:
        for pat in ["updateSingleCheckoutPaymentFailure", "cancelPayment"]:
            for m in re.finditer(re.escape(pat), txt):
                s = max(0, m.start() - 600)
                e = min(len(txt), m.end() + 600)
                out.append(f"===== {f.name} [{pat}] =====")
                out.append(txt[s:e])
                out.append("")

Path(__file__).resolve().parent.joinpath("grep_payment_failure_out.txt").write_text(
    "\n".join(out), encoding="utf-8")
print("OK -> grep_payment_failure_out.txt")
