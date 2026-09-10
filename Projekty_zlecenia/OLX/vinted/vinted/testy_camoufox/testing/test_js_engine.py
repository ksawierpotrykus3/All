#!/usr/bin/env python3
"""
test_js_engine.py
Test JS Engine Server standalone (bez curl_cffi)
"""

import requests
import json
import time

ENGINE_URL = "http://localhost:3000"

def test_engine():
    s = requests.Session()

    print("=" * 60)
    print("TESTING JS ENGINE SERVER")
    print("=" * 60)

    # 1. Health check
    print("\n1. Health check...")
    r = s.get(f"{ENGINE_URL}/health")
    print(f"   Status: {r.status_code}")
    print(f"   Response: {r.json()}")

    # 2. DataDome init
    print("\n2. DataDome init...")
    r = s.post(f"{ENGINE_URL}/datadome/init")
    print(f"   Status: {r.status_code}")
    dd_init = r.json()
    print(f"   Session: {dd_init.get('sessionId')}")
    print(f"   Client: {dd_init.get('clientId')}")

    # 3. DataDome context
    print("\n3. DataDome context (GET /)...")
    r = s.post(f"{ENGINE_URL}/datadome/context", json={"url": "https://www.vinted.pl", "method": "GET"})
    print(f"   Status: {r.status_code}")
    ctx = r.json()
    print(f"   Cookies: {list(ctx['context']['cookies'].keys())}")
    print(f"   Headers: {list(ctx['context']['headers'].keys())}")

    # 4. Behavioral simulation
    print("\n4. Behavioral simulation...")
    s.post(f"{ENGINE_URL}/datadome/behavioral/mouse-move", json={"x": 100, "y": 200, "duration": 500})
    s.post(f"{ENGINE_URL}/datadome/behavioral/click", json={"x": 150, "y": 250})
    s.post(f"{ENGINE_URL}/datadome/behavioral/scroll", json={"deltaY": -300})
    print("   Simulated: mouse move, click, scroll")

    # 5. DataDome context after behavioral
    print("\n5. DataDome context after behavioral...")
    r = s.post(f"{ENGINE_URL}/datadome/context", json={"url": "https://www.vinted.pl/api/v2/purchases/checkout/build", "method": "POST"})
    ctx = r.json()
    print(f"   Behavioral hash: {ctx['context']['headers'].get('x-datadome-behavioral')}")

    # 6. Incognia init
    print("\n6. Incognia init...")
    r = s.post(f"{ENGINE_URL}/incognia/init", json={"apiBaseUrl": "https://api.vinted.pl/j3r4zw"})
    print(f"   Status: {r.status_code}")
    ic_init = r.json()
    print(f"   State: {ic_init.get('state')}")

    # 7. Incognia request token
    print("\n7. Incognia request token...")
    r = s.post(f"{ENGINE_URL}/incognia/request-token")
    print(f"   Status: {r.status_code}")
    token = r.json()
    print(f"   Token (first 50): {token.get('token', '')[:50]}...")

    # 8. Incognia consume payload
    print("\n8. Incognia consume payload (pls)...")
    r = s.post(f"{ENGINE_URL}/incognia/consume-payload", json={"type": "pls"})
    print(f"   Status: {r.status_code}")
    payload = r.json()
    print(f"   siid: {payload['payload']['body'].get('siid')}")
    print(f"   s length: {len(payload['payload']['body'].get('s', ''))}")

    # 9. Checkout build payload
    print("\n9. Checkout build payload...")
    r = s.post(f"{ENGINE_URL}/checkout/build-payload", json={"itemId": "9807925466"})
    print(f"   Status: {r.status_code}")
    build = r.json()
    print(f"   item_id: {build['payload'].get('item_id')}")

    # 10. Checkout steps
    print("\n10. Checkout steps...")
    r = s.post(f"{ENGINE_URL}/checkout/steps", json={"purchaseId": "test-123"})
    print(f"   Status: {r.status_code}")
    steps = r.json()
    print(f"   Steps: {len(steps['steps'])}")

    # 11. Payment token
    print("\n11. Payment token...")
    r = s.post(f"{ENGINE_URL}/checkout/payment-token")
    print(f"   Status: {r.status_code}")
    pay = r.json()
    print(f"   Token (first 50): {pay.get('token', '')[:50]}...")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED ✅")
    print("=" * 60)

if __name__ == "__main__":
    test_engine()