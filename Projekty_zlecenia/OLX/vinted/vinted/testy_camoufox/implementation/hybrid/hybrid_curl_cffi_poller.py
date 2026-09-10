#!/usr/bin/env python3
"""
CurlCffiPoller - komponent do polling catalog/items i checkout/build
używający tokenów z TokenStore (odświeżanych przez CamoufoxTokenRefresher).

Funkcje:
1. Polling /api/v2/catalog/items (szybki, 247ms, zero DataDome blokad)
2. Checkout/build na żądanie (używa świeżych tokenów z TokenStore)
3. Auto-wait na tokeny jeśli nie ma ich jeszcze
4. Re-używa sesję curl_cffi z fingerprintem FF152
"""

import time
import json
import signal
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from curl_cffi import requests

sys.path.insert(0, str(Path(__file__).parent))
from hybrid_token_store import TokenStore, TokenSnapshot, token_store


# Firefox 152 fingerprint (zmierzony i zweryfikowany)
FF152_JA3 = "771,4865-4867-4866-49195-49199-52393-52392-49196-49200-49162-49171-49172-156-157-47-53,0-23-65281-10-11-35-16-5-34-18-51-43-13-45-28-27-65037,4588-29-23-24-25-256-257,0"
FF152_AKAMAI = "1:65536;2:0;4:131072;5:16384|12517377|0|m,p,a,s"
FF152_EXTRA_FP = {
    "tls_delegated_credential": "ecdsa_secp256r1_sha256:ecdsa_secp384r1_sha384:ecdsa_secp521r1_sha512:ecdsa_sha1",
    "tls_record_size_limit": 16385,
    "tls_cert_compression": "zstd",
}
FF152_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0"


# Endpointy
CATALOG_URL = "https://www.vinted.pl/api/v2/catalog/items"
CHECKOUT_BUILD_URL = "https://www.vinted.pl/api/v2/purchases/checkout/build"
CHECKOUT_PAYMENT_URL_TEMPLATE = "https://www.vinted.pl/api/v2/purchases/{purchase_id}/checkout/payment"

# Domyślny payload dla checkout/build
DEFAULT_CHECKOUT_PAYLOAD = {"purchase_items": [{"id": 21872241924, "type": "transaction"}]}


@dataclass
class PollResult:
    success: bool
    status_code: int
    data: Optional[Dict] = None
    error: Optional[str] = None
    response_time_ms: float = 0


class CurlCffiPoller:
    def __init__(self, 
                 token_store: TokenStore = token_store,
                 poll_interval_sec: float = 30.0,
                 token_wait_timeout: float = 60.0,
                 max_token_age_sec: float = 300.0):
        self.token_store = token_store
        self.poll_interval = poll_interval_sec
        self.token_wait_timeout = token_wait_timeout
        self.max_token_age = max_token_age_sec
        
        self.session = None
        self.running = False
        self.poll_count = 0
        self.last_poll_time = 0
        self.checkout_count = 0
        
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        print(f"\n[Poller] Received signal {signum}, shutting down...")
        self.stop()
    
    def _build_session(self) -> requests.Session:
        """Buduje sesję curl_cffi z fingerprintem FF152."""
        session = requests.Session()
        session.headers.update({
            "User-Agent": FF152_UA,
            "Accept": "application/json,text/plain,*/*,image/webp",
            "Accept-Language": "pl,en-US;q=0.9,en;q=0.8,ru;q=0.7",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Content-Type": "application/json",
            "Origin": "https://www.vinted.pl",
            "Sec-Ch-Ua": '"Not;A=Brand";v="8", "Chromium";v="150", "Opera GX";v="134"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Priority": "u=3",
            "Locale": "pl-PL",
        })
        return session
    
    def _apply_tokens(self, session: requests.Session, snapshot: TokenSnapshot):
        """Aplikuje tokeny z TokenStore do sesji."""
        session.headers.update({
            "X-Anon-Id": snapshot.x_anon_id,
            "X-Csrf-Token": snapshot.x_csrf_token,
            "X-Incognia-Request-Token": snapshot.x_incognia_request_token,
        })
        
        # Cookies
        for name, value in snapshot.cookies.items():
            session.cookies.set(name, value, domain=".vinted.pl")
    
    def _wait_for_valid_token(self, timeout: float = None) -> Optional[TokenSnapshot]:
        """Czeka na ważny token w TokenStore."""
        timeout = timeout or self.token_store._write_raw  # placeholder, use param
        timeout = getattr(self, 'token_wait_timeout', 60.0)
        
        print(f"[Poller] Waiting for valid token (timeout: {timeout}s)...")
        start = time.time()
        
        while time.time() - start < timeout:
            snapshot = self.token_store.get_tokens()
            if snapshot and self.token_store.is_token_valid(self.max_token_age):
                age = time.time() - snapshot.timestamp
                print(f"[Poller] Got valid token (age: {age:.0f}s, refresh #{snapshot.__dict__.get('refresh_count', '?')})")
                return snapshot
            
            time.sleep(1)
        
        return None
    
    def start(self):
        """Inicjalizuje sesję i czeka na pierwsze tokeny."""
        print("[Poller] Starting...")
        print(f"[Poller] Poll interval: {self.poll_interval}s")
        print(f"[Poller] Max token age: {self.max_token_age}s")
        
        self.session = self._build_session()
        
        # Czekaj na pierwsze tokeny od Refreshera
        print("[Poller] Waiting for first tokens from Refresher...")
        snapshot = self._wait_for_valid_token()
        if not snapshot:
            print("[Poller] ❌ Timeout waiting for tokens")
            return False
        
        self._apply_tokens(self.session, snapshot)
        print("[Poller] ✅ Initial tokens applied, ready to poll")
        return True
    
    def poll_catalog(self, params: Dict[str, Any] = None) -> PollResult:
        """Wykonuje polling catalog/items."""
        if not self._ensure_fresh_token():
            return PollResult(False, 0, error="No valid token")
        
        default_params = {
            "page": 1,
            "per_page": 20,
            "order": "newest_first",
            "catalog_ids": "",
            "color_ids": "",
            "brand_ids": "",
            "size_ids": "",
            "material_ids": "",
            "video_game_rating_ids": "",
            "status_ids": "",
            "is_for_swap": 0,
            "price_from": "",
            "price_to": "",
            "currency": "PLN",
        }
        if params:
            default_params.update(params)
        
        start = time.time()
        try:
            resp = self.session.get(
                CATALOG_URL,
                params=default_params,
                impersonate="firefox133",
                ja3=FF152_JA3,
                akamai=FF152_AKAMAI,
                extra_fp=FF152_EXTRA_FP,
                timeout=15,
            )
            elapsed = (time.time() - start) * 1000
            
            if resp.status_code == 200:
                return PollResult(True, 200, resp.json(), response_time_ms=elapsed)
            elif resp.status_code == 403:
                # DataDome block - tokeny wygasły lub DataDome challenge
                print(f"[Poller] ⚠️ 403 DataDome - tokens may be stale")
                # Wymuś odświeżenie tokenów (Refresher zrobi to w tle)
                self.token_store.add_error("Poller got 403 - tokens stale")
                return PollResult(False, 403, error="DataDome block")
            else:
                return PollResult(False, resp.status_code, error=f"HTTP {resp.status_code}")
                
        except Exception as e:
            return PollResult(False, 0, error=str(e))
    
    def _ensure_fresh_token(self) -> bool:
        """Sprawdza czy token jest świeży, jeśli nie - czeka na odświeżenie."""
        snapshot = self.token_store.get_tokens()
        if not snapshot or not self.token_store.is_token_valid(self.max_token_age):
            print("[Poller] Token stale/missing, waiting for Refresher...")
            snapshot = self._wait_for_valid_token()
            if snapshot:
                self._apply_tokens(self.session, snapshot)
                return True
            return False
        return True
    
    def checkout_build(self, payload: Dict = None) -> PollResult:
        """Wykonuje checkout/build z aktualnymi tokenami."""
        if not self._ensure_fresh_token():
            return PollResult(False, 0, error="No valid token for checkout")
        
        payload = payload or DEFAULT_CHECKOUT_PAYLOAD
        
        print(f"[Poller] Executing checkout/build...")
        start = time.time()
        
        try:
            resp = self.session.post(
                CHECKOUT_BUILD_URL,
                json=payload,
                impersonate="firefox133",
                ja3=FF152_JA3,
                akamai=FF152_AKAMAI,
                extra_fp=FF152_EXTRA_FP,
                timeout=30,
            )
            elapsed = (time.time() - start) * 1000
            
            if resp.status_code == 200:
                self.checkout_count += 1
                data = resp.json()
                purchase_id = data.get("purchase_id") or data.get("id")
                print(f"[Poller] ✅ Checkout/build SUCCESS (purchase_id: {purchase_id}, {elapsed:.0f}ms)")
                return PollResult(True, 200, data, response_time_ms=elapsed)
            elif resp.status_code == 403:
                print(f"[Poller] ❌ Checkout 403 - DataDome block or stale token")
                self.token_store.add_error("Checkout got 403")
                return PollResult(False, 403, error="DataDome block")
            else:
                return PollResult(False, resp.status_code, error=f"HTTP {resp.status_code}: {resp.text[:200]}")
                
        except Exception as e:
            return PollResult(False, 0, error=str(e))
    
    def checkout_payment(self, purchase_id: str, payment_payload: Dict = None) -> PollResult:
        """Wykonuje checkout/payment."""
        if not self._ensure_fresh_token():
            return PollResult(False, 0, error="No valid token for payment")
        
        url = CHECKOUT_PAYMENT_URL_TEMPLATE.format(purchase_id=purchase_id)
        default_payload = {
            "checksum": "auto",  # trzeba policzyć lub pobrać z build response
            "payment_options": {
                "browser_info": {
                    "language": "pl",
                    "color_depth": 24,
                    "java_enabled": False,
                    "screen_height": 1080,
                    "screen_width": 1920,
                    "timezone_offset": -120,
                }
            }
        }
        if payment_payload:
            default_payload.update(payment_payload)
        
        print(f"[Poller] Executing checkout/payment for {purchase_id}...")
        start = time.time()
        
        try:
            resp = self.session.post(
                url,
                json=default_payload,
                impersonate="firefox133",
                ja3=FF152_JA3,
                akamai=FF152_AKAMAI,
                extra_fp=FF152_EXTRA_FP,
                timeout=30,
            )
            elapsed = (time.time() - start) * 1000
            
            if resp.status_code == 200:
                print(f"[Poller] ✅ Payment SUCCESS ({elapsed:.0f}ms)")
                return PollResult(True, 200, resp.json(), response_time_ms=elapsed)
            else:
                return PollResult(False, resp.status_code, error=f"HTTP {resp.status_code}")
                
        except Exception as e:
            return PollResult(False, 0, error=str(e))
    
    def run_poll_loop(self):
        """Główna pętla pollingu catalog/items."""
        print(f"[Poller] Starting poll loop (interval: {self.poll_interval}s)...")
        
        while True:
            try:
                result = self.poll_catalog()
                self.poll_count += 1
                self.last_poll_time = time.time()
                
                if result.success:
                    items_count = len(result.data.get("items", [])) if result.data else 0
                    print(f"[Poller] Poll #{self.poll_count}: {items_count} items ({result.response_time_ms:.0f}ms)")
                else:
                    print(f"[Poller] Poll #{self.poll_count} FAILED: {result.error}")
                    
            except Exception as e:
                print(f"[Poller] Poll error: {e}")
            
            # Sleep z podziałem na kawałki dla responsywności stop()
            elapsed = 0
            while elapsed < self.poll_interval:
                time.sleep(min(5, self.poll_interval - elapsed))
                elapsed += 5
                # Tu można dodać check self.running jeśli dodamy flagę
    
    def stop(self):
        print("[Poller] Stopping...")
        if self.session:
            self.session.close()


def demo_single_checkout():
    """Demo: pojedynczy checkout/build (dla testów)."""
    poller = CurlCffiPoller()
    
    if not poller.start():
        return
    
    # Test checkout
    result = poller.checkout_build()
    print(f"Checkout result: {result.success}, {result.error or 'OK'}")
    
    if result.success and result.data:
        purchase_id = result.data.get("purchase_id") or result.data.get("id")
        print(f"Purchase ID: {purchase_id}")
        
        # Test payment (opcjonalnie)
        # payment_result = poller.checkout_payment(purchase_id)
        # print(f"Payment: {payment_result.success}")


if __name__ == "__main__":
    # Uruchom jako demo lub poll loop
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["demo", "poll"], default="demo")
    parser.add_argument("--interval", type=float, default=30.0)
    args = parser.parse_args()
    
    poller = CurlCffiPoller(poll_interval_sec=args.interval)
    
    if not poller.start():
        sys.exit(1)
    
    if args.mode == "demo":
        demo_single_checkout()
    else:
        poller.run_poll_loop()