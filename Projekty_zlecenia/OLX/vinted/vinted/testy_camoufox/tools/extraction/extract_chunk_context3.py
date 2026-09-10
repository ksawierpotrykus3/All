# coding: utf-8
"""extract_chunk_context3.py — find where navigateToCheckout / useNavigateToCheckout
is used, and how the id (order_id/transaction_id) is obtained before build.
"""
import re
from pathlib import Path

CHUNK = Path(r"f:\PROJEKTY\vinted\vinted\dane\chunks\0~~ak8p40jr.6.js")
text = CHUNK.read_text(encoding="utf-8", errors="replace")

PATTERNS = [
    (r"useNavigateToCheckout", 150, 300),
    (r"navigateToCheckout", 200, 200),
    (r"createTransaction|createPurchase|startTransaction|createCheckout|initiateCheckout", 200, 250),
    (r"conversations", 200, 250),
    (r"transactionId|transaction_id|orderId|order_id", 150, 150),
]

for pat, pre, post in PATTERNS:
    print("=" * 100)
    print(f"PATTERN: {pat}")
    count = 0
    for m in re.finditer(pat, text):
        start = max(0, m.start() - pre)
        end = min(len(text), m.end() + post)
        print("-" * 80)
        print(text[start:end])
        print()
        count += 1
        if count >= 10:
            break
    if count == 0:
        print("(no matches)")
    print()
