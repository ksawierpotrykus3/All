# coding: utf-8
"""Szukaj w chunkach JS: cancel / anulowanie transakcji / checkout."""
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent / "chunks_har"
out = []
pats = ["cancel", "Cancel", "anuluj", "cancelTransaction", "cancel_transaction",
        "DELETE", "delete_transaction", "cancel_checkout", "cancelCheckout"]
for f in sorted(BASE.glob("*.js")):
    txt = f.read_text(encoding="utf-8", errors="ignore")
    for pat in ["cancelTransaction", "cancel_transaction", "delete_transaction",
                "cancelCheckout", "cancel_checkout", "transactions/", "delete_transaction"]:
        if pat in txt:
            for m in re.finditer(re.escape(pat), txt):
                s = max(0, m.start() - 150)
                e = min(len(txt), m.end() + 150)
                out.append(f"===== {f.name} [{pat}] =====")
                out.append(txt[s:e])
                break
            break
(BASE / "..").resolve()
Path(BASE_DIR := Path(__file__).resolve().parent, "grep_cancel_out.txt").write_text("\n".join(out), encoding="utf-8")
print("OK -> grep_cancel_out.txt")
