import re
import json
from pathlib import Path

chunks_dir = Path("dane/chunks")
checkout_file = chunks_dir / "108_fn4d86.ek.js"
if not checkout_file.exists():
    # find files containing Checkout
    for f in chunks_dir.glob("*.js"):
        c = f.read_text(encoding="utf-8", errors="ignore")
        if "CheckoutErrorCode" in c or "PaymentOptionsView" in c:
            checkout_file = f
            break

print(f"Analyzing main checkout bundle: {checkout_file.name}")
content = checkout_file.read_text(encoding="utf-8", errors="ignore")

# Extract all exported enum names and keys
enums = re.findall(r'e\.s\(\[([^\]]+)\]\)', content)
print(f"\nFound {len(enums)} enum/constant exports:")
for exp in enums[:20]:
    print("  Export:", exp[:150])

# Extract all strings matching URL/API/action patterns
strings = set(re.findall(r'["\']([a-zA-Z0-9_\-\/]{3,60})["\']', content))
print(f"\nTotal unique string literals: {len(strings)}")

interesting = [s for s in strings if any(k in s.lower() for k in ["checkout", "transaction", "payment", "shipment", "address", "wallet", "balance", "card", "order", "buyer", "seller", "escrow", "invoice", "bank", "blik", "inpost", "locker", "carrier"])]
print(f"\nInteresting domain terms found ({len(interesting)}):")
for s in sorted(interesting):
    print("  ->", s)
