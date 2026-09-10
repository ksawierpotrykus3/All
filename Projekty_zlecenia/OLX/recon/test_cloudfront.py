# coding: utf-8
"""Prototyp testu CloudFront + skanowania ID OLX (faza 0)."""
import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

headers = {
    "User-Agent": UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
    "Referer": "https://www.olx.pl/",
}

def test(url):
    try:
        r = requests.get(url, headers=headers, timeout=15)
        print(f"{r.status_code}  size={len(r.content)}  {url}")
        if r.status_code == 200:
            print("   BODY_head:", r.text[:120].replace("\n", " "))
        return r
    except Exception as e:
        print(f"ERR {url}: {e}")
        return None

print("=== TEST 1: strona glowna ===")
test("https://www.olx.pl/")

print("=== TEST 2: API lista ===")
test("https://www.olx.pl/api/v1/offers/?offset=0&limit=2")

print("=== TEST 3: API pojedyncza oferta (ID numeryczne) ===")
test("https://www.olx.pl/api/v1/offers/1093494000/")