import re
from curl_cffi import requests as creq

url = "https://www.olx.pl/app/static/js/olxeuweb.ad.d.ad-buy-with-delivery.94038596b.chunk.js"
r = creq.get(url, impersonate="chrome124")
print("Chunk size:", len(r.text))

# Search for API paths
paths = set(re.findall(r'/api/v\d+/[a-zA-Z0-9_\-/]+', r.text))
for p in sorted(paths):
    print("API PATH:", p)

# Search for checkout/delivery URLs
all_urls = set(re.findall(r'/[a-zA-Z0-9_\-/]*(?:delivery|checkout|order|buy|payment)[a-zA-Z0-9_\-/]*', r.text, re.IGNORECASE))
for u in sorted(all_urls)[:30]:
    print("URL PATH:", u)
