import re
from curl_cffi import requests as creq

url = 'https://www.olx.pl/app/static/js/olxeuweb.ad.d.ad-buy-with-delivery.94038596b.chunk.js'
t = creq.get(url, impersonate='chrome124').text
strs = re.findall(r'"([^"]{3,60})"', t)
for s in sorted(set(strs)):
    if any(k in s.lower() for k in ['delivery', 'buy', 'order', 'href', 'url', 'platnosc', 'paczka', 'safetransaction', 'checkout']):
        print('STRING:', s)
