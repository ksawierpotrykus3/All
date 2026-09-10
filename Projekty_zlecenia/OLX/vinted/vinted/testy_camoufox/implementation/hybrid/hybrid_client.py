#!/usr/bin/env python3
"""
hybrid_client.py
Python wrapper dla curl_cffi używający JS Engine Server (Node.js)
"""

import json
import time
import subprocess
import requests
from curl_cffi import requests as curl_requests
from curl_cffi import BrowserType

ENGINE_URL = "http://localhost:3000"

class JSEngineClient:
    """Klient HTTP do JS Engine Server"""

    def __init__(self, base_url=ENGINE_URL):
        self.base_url = base_url
        self.session = requests.Session()

    def call(self, endpoint, method="POST", data=None):
        url = f"{self.base_url}{endpoint}"
        try:
            if method == "GET":
                resp = self.session.get(url, timeout=10)
            else:
                resp = self.session.post(url, json=data, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            raise RuntimeError(f"JS Engine call failed ({endpoint}): {e}")

    # === DataDome ===
    def datadome_init(self, fingerprint=None):
        return self.call("/datadome/init", data={"fingerprint": fingerprint})

    def datadome_context(self, url, method):
        return self.call("/datadome/context", data={"url": url, "method": method})

    def datadome_mouse_move(self, x, y, duration=500):
        return self.call("/datadome/behavioral/mouse-move", data={"x": x, "y": y, "duration": duration})

    def datadome_click(self, x, y):
        return self.call("/datadome/behavioral/click", data={"x": x, "y": y})

    def datadome_scroll(self, delta_y):
        return self.call("/datadome/behavioral/scroll", data={"deltaY": delta_y})

    def datadome_key_press(self, key):
        return self.call("/datadome/behavioral/key-press", data={"key": key})

    def datadome_beacon(self):
        return self.call("/datadome/beacon", method="GET")

    # === Incognia ===
    def incognia_init(self, config=None):
        return self.call("/incognia/init", data=config or {})

    def incognia_request_token(self):
        return self.call("/incognia/request-token")

    def incognia_consume_payload(self, type="pls"):
        return self.call("/incognia/consume-payload", data={"type": type})

    def incognia_interaction(self, interaction):
        return self.call("/incognia/interaction", data=interaction)

    def incognia_state(self):
        return self.call("/incognia/state", method="GET")

    # === Checkout ===
    def checkout_build_payload(self, item_id, quantity=1, fingerprint=None):
        return self.call("/checkout/build-payload", data={
            "itemId": item_id,
            "quantity": quantity,
            "fingerprint": fingerprint
        })

    def checkout_steps(self, purchase_id):
        return self.call("/checkout/steps", data={"purchaseId": purchase_id})

    def checkout_payment_token(self, checksum=None):
        return self.call("/checkout/payment-token", data={"checksum": checksum})


class HybridClient:
    """
    Główny klient hybrydowy: curl_cffi + JS Engine
    """

    def __init__(self, impersonate=BrowserType.chrome146):
        self.js = JSEngineClient()
        self.curl = curl_requests.Session()
        self.impersonate = impersonate
        self.cookies = {}
        self.headers = {}

    def start_engines(self, fingerprint=None):
        """Inicjalizuj oba silniki"""
        print("[Hybrid] Initializing DataDome...")
        self.js.datadome_init(fingerprint)

        print("[Hybrid] Initializing Incognia...")
        self.js.incognia_init()

        # Pobierz początkowe cookies/headers z DataDome
        ctx = self.js.datadome_context("https://www.vinted.pl", "GET")
        self.cookies.update(ctx["context"]["cookies"])
        self.headers.update(ctx["context"]["headers"])

        self.curl.cookies.update(self.cookies)
        self.curl.headers.update(self.headers)

        print("[Hybrid] Engines ready")

    def simulate_behavior_before_click(self):
        """Symuluj zachowanie użytkownika przed kliknięciem 'Kup teraz'"""
        print("[Hybrid] Simulating user behavior...")
        # Ruch myszy do przycisku
        self.js.datadome_mouse_move(960, 540, 800)
        self.js.datadome_mouse_move(1200, 800, 600)
        # Kliknięcie
        self.js.datadome_click(1250, 820)
        # Scroll
        self.js.datadome_scroll(-300)
        # Odśwież kontekst po behavioral
        ctx = self.js.datadome_context("https://www.vinted.pl/api/v2/purchases/checkout/build", "POST")
        self.cookies.update(ctx["context"]["cookies"])
        self.headers.update(ctx["context"]["headers"])
        self.curl.cookies.update(self.cookies)
        self.curl.headers.update(self.headers)

    def checkout_item(self, item_id):
        """Pełny flow checkoutu dla itemu"""
        print(f"[Hybrid] Starting checkout for item {item_id}")

        # 1. Symuluj behavioral przed requestem
        self.simulate_behavior_before_click()

        # 2. GET item page (opcjonalnie - dla referer/cookies)
        print("[Hybrid] GET item page...")
        resp = self.curl.get(
            f"https://www.vinted.pl/items/{item_id}",
            impersonate=self.impersonate,
            timeout=30
        )
        print(f"  GET status: {resp.status_code}")

        # 3. POST /checkout/build
        print("[Hybrid] POST /checkout/build...")
        build_data = self.js.checkout_build_payload(item_id)
        payload = build_data["payload"]

        # Dodaj incognia token
        incognia_token = self.js.incognia_request_token()
        self.headers["x-incognia-request-token"] = incognia_token["token"]
        self.curl.headers.update(self.headers)

        resp = self.curl.post(
            "https://www.vinted.pl/api/v2/purchases/checkout/build",
            json=payload,
            impersonate=self.impersonate,
            timeout=30
        )
        print(f"  POST status: {resp.status_code}")
        print(f"  Response: {resp.text[:200]}")

        if resp.status_code != 200:
            return {"success": False, "step": "build", "status": resp.status_code, "response": resp.text}

        data = resp.json()
        purchase_items = data.get("purchase_items", [])
        if not purchase_items:
            return {"success": False, "step": "build", "error": "No purchase_items"}

        purchase_id = purchase_items[0].get("id")
        print(f"  ✅ Got purchase_id: {purchase_id}")

        # 4. PUT /checkout steps
        print("[Hybrid] Executing checkout steps...")
        steps_data = self.js.checkout_steps(purchase_id)
        for i, step in enumerate(steps_data["steps"]):
            print(f"  Step {i+1}: {step['endpoint']}")
            resp = self.curl.put(
                f"https://www.vinted.pl{step['endpoint'].split(' ')[1]}",
                json=step["body"],
                impersonate=self.impersonate,
                timeout=30
            )
            print(f"    Status: {resp.status_code}")
            if resp.status_code >= 400:
                return {"success": False, "step": f"checkout_{i+1}", "status": resp.status_code, "response": resp.text}

        # 5. POST /checkout/payment
        print("[Hybrid] POST /checkout/payment...")
        payment_data = self.js.checkout_payment_token()
        self.headers["x-incognia-request-token"] = payment_data["token"]
        self.curl.headers.update(self.headers)

        resp = self.curl.post(
            f"https://www.vinted.pl/api/v2/purchases/{purchase_id}/checkout/payment",
            json=payment_data["paymentBody"],
            impersonate=self.impersonate,
            timeout=30
        )
        print(f"  Status: {resp.status_code}")
        print(f"  Response: {resp.text[:300]}")

        if resp.status_code == 200:
            return {"success": True, "purchase_id": purchase_id, "result": resp.json()}
        else:
            return {"success": False, "step": "payment", "status": resp.status_code, "response": resp.text}


def main():
    import sys
    item_id = sys.argv[1] if len(sys.argv) > 1 else "9807925466"

    client = HybridClient(impersonate=BrowserType.chrome146)

    try:
        client.start_engines()
        result = client.checkout_item(item_id)
        print(f"\n[Hybrid] Final result: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"[Hybrid] Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()