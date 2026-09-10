# coding: utf-8
"""Test endpointu partnerskiego /api/partner/adverts z nagłówkiem Version."""
import json
from curl_cffi import requests as creq

IMP = "chrome124"
CLIENT_ID = "202745"
CLIENT_SECRET = "HucUsS3hhReAr5j5V4BN5I85rlOM0y2y5cFGoKjJbXuPO5YI"

def get_token():
    r = creq.post("https://www.olx.pl/api/open/oauth/token",
                  data=json.dumps({
                      "grant_type": "client_credentials",
                      "client_id": CLIENT_ID,
                      "client_secret": CLIENT_SECRET,
                      "scope": "v2 read write",
                  }),
                  headers={"Content-Type": "application/json"},
                  impersonate=IMP, timeout=20)
    return r.json().get("access_token")

def test_adverts(token, version):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "Version": version,
    }
    body = {
        "offset": 0,
        "limit": 3,
        "query": "iphone",
    }
    try:
        r = creq.post("https://www.olx.pl/api/partner/adverts",
                      data=json.dumps(body), headers=headers,
                      impersonate=IMP, timeout=20)
        return r.status_code, r.text
    except Exception as e:
        return -1, str(e)

if __name__ == "__main__":
    token = get_token()
    print("Token OK" if token else "Brak tokenu")

    for v in ["2.0", "v2", "1.0", "2", "1", "3.0", "2024-01-01"]:
        code, body = test_adverts(token, v)
        print(f"\n=== Version={v} ===")
        print(f"  code={code}")
        print(f"  body={body[:400]}")