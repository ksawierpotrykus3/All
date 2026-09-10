import re
import json
from pathlib import Path

chunks_dir = Path("dane/chunks")
chunk_files = list(chunks_dir.glob("*.js"))
print(f"Analyzing {len(chunk_files)} downloaded chunks...")

api_snippets = []
checkout_snippets = []
payment_snippets = []

for f in chunk_files:
    content = f.read_text(encoding="utf-8", errors="ignore")
    
    # Find api/v2 mentions
    for m in re.finditer(r'api/v2/([a-zA-Z0-9_\-\/]+)', content):
        api_snippets.append(m.group(0))
        
    # Find api endpoints with template literals or variables
    for m in re.finditer(r'[\'"`]/api/[^\'"`\n\r]{1,80}[\'"`]', content):
        api_snippets.append(m.group(0))
        
    # Find checkout or buy function/path patterns
    for m in re.finditer(r'[\'"`]/checkout/[^\'"`\n\r]{1,80}[\'"`]', content):
        checkout_snippets.append(m.group(0))
        
    for m in re.finditer(r'[\'"`]/transaction[s]?/[^\'"`\n\r]{1,80}[\'"`]', content):
        checkout_snippets.append(m.group(0))
        
    # Search for action handlers
    for m in re.finditer(r'(?:createOrder|createTransaction|initiateCheckout|buyItem|confirmPayment|submitPayment)[a-zA-Z0-9_]*', content):
        payment_snippets.append(m.group(0))

print("\n=== ZNALEZIONE ENDPOINTY API (api/...) ===")
unique_apis = sorted(list(set(api_snippets)))
print(f"Znaleziono {len(unique_apis)} unikalnych wzorców API:")
for a in unique_apis:
    print(" ", a)

print("\n=== ZNALEZIONE ŚCIEŻKI CHECKOUT / TRANSACTIONS ===")
unique_checkouts = sorted(list(set(checkout_snippets)))
print(f"Znaleziono {len(unique_checkouts)} unikalnych ścieżek checkout:")
for c in unique_checkouts:
    print(" ", c)

print("\n=== ZNALEZIONE FUNKCJE PŁATNOŚCI / TRANSAKCJI ===")
unique_payments = sorted(list(set(payment_snippets)))
print(f"Znaleziono {len(unique_payments)} unikalnych funkcji:")
for p in unique_payments:
    print(" ", p)
