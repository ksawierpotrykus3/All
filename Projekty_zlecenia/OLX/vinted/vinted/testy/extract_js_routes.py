import re
import json
from pathlib import Path
from curl_cffi import requests as creq

html_path = Path(r"c:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\vinted\dane\katalog_1904.html")
if not html_path.exists():
    print("HTML not found")
    exit(1)

text = html_path.read_text(encoding="utf-8", errors="ignore")
print(f"HTML size: {len(text)} bytes")

# Extract scripts
scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', text)
print(f"Found {len(scripts)} scripts:")
for s in scripts:
    print("  Script:", s)

# Let's inspect Next.js buildId or manifest
build_id_m = re.search(r'"buildId":"([^"]+)"', text)
if build_id_m:
    print("Build ID:", build_id_m.group(1))

# Check for API paths in HTML text
api_paths = set(re.findall(r'/(?:api|checkout|transactions|orders|items|catalog)/[a-zA-Z0-9_\-\/]+', text))
print(f"\nFound {len(api_paths)} potential API paths directly in HTML:")
for p in sorted(api_paths):
    print("  Path:", p)
