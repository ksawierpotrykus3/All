# coding: utf-8
"""extract_more_chunks.py — inspect how navigateToCheckout is used in other chunks,
and how conversations (transaction creation) is triggered from the frontend.
"""
import re
from pathlib import Path

BASE = Path(r"f:\PROJEKTY\vinted\vinted\dane\chunks")

FILES = [
    (BASE / "03.r8h2o1vqzm.js", [r"navigateToCheckout", r"useNavigateToCheckout"]),
    (BASE / "14fxopprmcbmi.js", [r"conversations"]),
    (BASE / "0ms205~nooizz.js", [r"conversations"]),
    (BASE / "0fsh1_qbrfm3l.js", [r"conversations"]),
    (BASE / "0c3ke5w13nf6o.js", [r"conversations"]),
]

for path, pats in FILES:
    print("=" * 100)
    print(f"### {path.name}")
    text = path.read_text(encoding="utf-8", errors="replace")
    print(f"size: {len(text)} chars")
    for pat in pats:
        print(f"--- pattern: {pat}")
        count = 0
        for m in re.finditer(pat, text):
            start = max(0, m.start() - 300)
            end = min(len(text), m.end() + 350)
            print("-" * 80)
            print(text[start:end])
            print()
            count += 1
            if count >= 5:
                break
        if count == 0:
            print("(no matches)")
