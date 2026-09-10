# coding: utf-8
"""Test curl_cffi (impersonacja TLS Chrome) vs CloudFront OLX."""
from curl_cffi import requests as creq

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

def test(impersonate, url):
    try:
        r = creq.get(url, impersonate=impersonate, timeout=15)
        print(f"[{impersonate}] {r.status_code} size={len(r.content)}  {url}")
        if r.status_code == 200:
            print("   BODY_head:", r.text[:150].replace("\n", " "))
        return r
    except Exception as e:
        print(f"[{impersonate}] ERR {url}: {e}")
        return None

url = "https://www.olx.pl/api/v1/offers/1093494000/"

for imp in ["chrome126", "chrome124", "chrome120", "chrome110", "chrome"]:
    test(imp, url)