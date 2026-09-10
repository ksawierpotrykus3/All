import re
import json
from pathlib import Path

target = Path("dane/chunks/0~~ak8p40jr.6.js")
content = target.read_text(encoding="utf-8", errors="ignore")
print(f"File: {target.name}, size: {len(content)}")

# Extract all string literals
strings = set(re.findall(r'["\']([a-zA-Z0-9_\-\/\.]{2,80})["\']', content))
print(f"Total unique strings: {len(strings)}")

domain_terms = [s for s in strings if any(k in s.lower() for k in ["checkout", "payment", "shipping", "address", "wallet", "card", "transaction", "escrow", "order", "delivery", "phone", "bank", "credit", "voucher", "balance", "carrier", "point", "locker", "pickup"])]
print(f"\nFound {len(domain_terms)} checkout/payment terms:")
for t in sorted(domain_terms):
    print("  ->", t)

# Search for network calls / fetch / urls
urls = [s for s in strings if "/" in s and not s.startswith("./") and not s.endswith(".js")]
print(f"\nFound {len(urls)} URL-like strings:")
for u in sorted(urls):
    print("  URL:", u)
