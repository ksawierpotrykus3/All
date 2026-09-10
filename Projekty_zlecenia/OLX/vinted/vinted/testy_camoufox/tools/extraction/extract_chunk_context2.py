# coding: utf-8
"""extract_chunk_context2.py — deeper inspection of module 401438 (the component
that calls initiateSingleCheckout) and navigateToSingleCheckout, to determine
whether build can be triggered from the listing (item_id) without conversations.
"""
import re
from pathlib import Path

CHUNK = Path(r"f:\PROJEKTY\vinted\vinted\dane\chunks\0~~ak8p40jr.6.js")
text = CHUNK.read_text(encoding="utf-8", errors="replace")


def show(label, start, end, max_chars=4500):
    print("=" * 100)
    print(f"### {label}  (chars {start}-{end})")
    print(text[start:end])
    print()


# 1. Module 401438: find its start (the module begins right after a module id marker)
i = text.find("401438,42718")
if i != -1:
    # show ~4000 chars AFTER the module marker to see the whole component
    show("MODULE 401438 (component calling initiateSingleCheckout)", i, i + 4500)
else:
    print("module 401438 marker not found")

# 2. Find call sites of the useCallback d( -> search for `(0,n.incrementCheckoutInitiate)` occurrences
print("=" * 100)
print("### occurrences of incrementCheckoutInitiate")
for m in re.finditer(r"incrementCheckoutInitiate", text):
    start = max(0, m.start() - 150)
    end = min(len(text), m.end() + 250)
    print("-" * 80)
    print(text[start:end])
    print()
