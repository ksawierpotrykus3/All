import re
import json
from pathlib import Path
from curl_cffi import requests as creq

s = creq.Session(impersonate="chrome124")

html_path = Path("dane/katalog_1904.html")
text = html_path.read_text(encoding="utf-8", errors="ignore")
scripts = re.findall(r'src=["\']([^"\']+\.js[^"\']*)["\']', text)

chunks_dir = Path("dane/chunks")
chunks_dir.mkdir(parents=True, exist_ok=True)

endpoints = set()
fetch_patterns = set()

print(f"Downloading and scanning {len(scripts)} JS chunks...")
for url in scripts:
    if not url.startswith("http"):
        url = "https://marketplace-web-assets.vinted.com" + url if url.startswith("/_next") else "https://www.vinted.pl" + url
    
    filename = url.split("/")[-1].split("?")[0]
    out_path = chunks_dir / filename
    
    try:
        if not out_path.exists():
            r = s.get(url, timeout=10)
            if r.status_code == 200:
                out_path.write_bytes(r.content)
            else:
                continue
                
        js_content = out_path.read_text(encoding="utf-8", errors="ignore")
        
        # Search for API endpoints
        apis = re.findall(r'["\'](?:/api/v2/[a-zA-Z0-9_\-\/]+|https://www\.vinted\.pl/api/v2/[a-zA-Z0-9_\-\/]+)["\']', js_content)
        for a in apis:
            endpoints.add(a.strip('"\''))
            
        # Search for checkout routes
        checkouts = re.findall(r'["\'](?:/checkout/[a-zA-Z0-9_\-\/]+|/transactions/[a-zA-Z0-9_\-\/]+|/orders/[a-zA-Z0-9_\-\/]+)["\']', js_content)
        for c in checkouts:
            endpoints.add(c.strip('"\''))
            
    except Exception as e:
        print(f"Error {filename}: {e}")

print(f"\n========================================================")
print(f"=== ZNALEZIONE PRAWDZIWE ENDPOINTY W KODZIE JS VINTED ===")
print(f"Łącznie znaleziono: {len(endpoints)} endpointów:")
for ep in sorted(endpoints):
    print("  ->", ep)

# Save to json
out_json = Path("dane/vinted_real_endpoints.json")
out_json.write_text(json.dumps(sorted(list(endpoints)), indent=2), encoding="utf-8")
print(f"\nZapisano do: {out_json}")
