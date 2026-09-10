import re
import json
from pathlib import Path
from curl_cffi import requests as creq

html_path = Path("dane/katalog_1904.html")
text = html_path.read_text(encoding="utf-8", errors="ignore")

# Find all scripts
scripts = re.findall(r'src=["\']([^"\']+\.js[^"\']*)["\']', text)
print(f"Total script tags found: {len(scripts)}")

vinted_scripts = []
for s in scripts:
    if "vinted" in s or "/_next/" in s or "web-app" in s or s.startswith("/"):
        full_url = s if s.startswith("http") else "https://www.vinted.pl" + s
        vinted_scripts.append(full_url)
        print("  ->", full_url)

# Let's search inside flight_data.txt for checkout/transaction/order patterns
flight_path = Path("dane/flight_data.txt")
if flight_path.exists():
    flight_text = flight_path.read_text(encoding="utf-8", errors="ignore")
    print(f"\nFlight data size: {len(flight_text)} bytes")
    
    # Find all API routes mentioned in flight data
    api_matches = set(re.findall(r'api/v2/[a-zA-Z0-9_\-\/]+', flight_text))
    print(f"Found {len(api_matches)} api/v2 routes in flight data:")
    for a in sorted(api_matches):
        print("   API:", a)
        
    # Check for checkout or transaction keys
    trans_matches = set(re.findall(r'[a-zA-Z0-9_]*(?:checkout|transaction|payment|order|shipment|wallet|balance|paczkomat|inpost)[a-zA-Z0-9_]*', flight_text, re.IGNORECASE))
    print(f"\nFound {len(trans_matches)} relevant terms in flight data:")
    for t in sorted(trans_matches)[:30]:
        print("   Term:", t)
