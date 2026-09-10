# coding: utf-8
"""Test OFICJALNEGO API partnerskiego OLX (klucz z rozmowy)."""
import json
from curl_cffi import requests as creq

IMP = "chrome124"
CLIENT_ID = "202745"
CLIENT_SECRET = "HucUsS3hhReAr5j5V4BN5I85rlOM0y2y5cFGoKjJbXuPO5YI"

# Endpointy OAuth OLX (różne wersje)
TOKEN_URLS = [
    "https://www.olx.pl/api/open/oauth/token",
    "https://www.olx.pl/api/partner/oauth/token",
    "https://auth.olx.pl/oauth/token",
]

def post_json(url, payload, headers=None):
    try:
        r = creq.post(url, data=json.dumps(payload), impersonate=IMP,
                      headers=headers or {}, timeout=20)
        return r.status_code, r.text
    except Exception as e:
        return -1, str(e)

def test_token(url):
    payload = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "v2 read write",
    }
    headers = {"Content-Type": "application/json"}
    code, body = post_json(url, payload, headers)
    print(f"\n=== TOKEN {url} ===")
    print(f"  code={code}")
    print(f"  body={body}")
    if code == 200:
        try:
            j = json.loads(body)
            return j.get("access_token")
        except Exception:
            return None
    return None

def test_partner_adverts(token):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    # Historyczny endpoint wyszukiwania partnerskiego
    for url in [
        "https://www.olx.pl/api/partner/adverts",
        "https://www.olx.pl/api/partner/offers",
    ]:
        code, body = post_json(url, {"offset": 0, "limit": 5}, headers)
        print(f"\n=== PARTNER {url} ===")
        print(f"  code={code}")
        print(f"  body={body}")

if __name__ == "__main__":
    print("Klient ID:", CLIENT_ID)
    token = None
    for u in TOKEN_URLS:
        token = test_token(u)
        if token:
            print("\n>>> UZYSKANO TOKEN:", token[:40], "...")
            break

    if token:
        test_partner_adverts(token)
    else:
        print("\n>>> Nie uzyskano tokenu z żadnego endpointu OAuth.")