# coding: utf-8
"""extract_chunk_context.py — extracts context windows around key patterns
in the minified JS chunk, to inspect whether checkout/build can be called
directly from the listing (without opening item page / conversations).

Usage: python extract_chunk_context.py
"""
import re
from pathlib import Path

CHUNK = Path(r"f:\PROJEKTY\vinted\vinted\dane\chunks\0~~ak8p40jr.6.js")
PATTERNS = [
    r"initiateSingleCheckout",
    r"purchase_items",
    r"type:\s*\"transaction\"",
    r"checkout/build",
    r"/conversations",
    r"initiator",
    r"instant",
    r"direct_buy|directBuy|instant_buy|instantBuy|fast_buy|fastBuy",
    r"type:\s*\"item\"",
]

WINDOW = 400  # chars before/after each match
MAX_PER_PATTERN = 6

text = CHUNK.read_text(encoding="utf-8", errors="replace")
print(f"chunk size: {len(text)} chars\n")

for pat in PATTERNS:
    print("=" * 100)
    print(f"PATTERN: {pat}")
    count = 0
    for m in re.finditer(pat, text):
        start = max(0, m.start() - WINDOW)
        end = min(len(text), m.end() + WINDOW)
        snippet = text[start:end]
        print("-" * 100)
        print(snippet)
        print()
        count += 1
        if count >= MAX_PER_PATTERN:
            break
    if count == 0:
        print("(no matches)")
    print()
