#!/usr/bin/env python3
"""
CamoufoxTokenRefresher - daemon uruchamiający Camoufox w tle,
odświeżający tokeny Incognia/DataDome co N minut.

Architektura:
- Persistent context (profil Firefox) - utrzymuje sesję
- Headless = True (można False do debugowania)
- Co REFRESH_INTERVAL_MIN minut:
  1. Otwiera item page
  2. Kliknie "Kup teraz" (isTrusted click)
  3. Przechwytuje x-incognia-request-token, cookies, DataDome headers
  4. Zapisuje do TokenStore
"""

import time
import json
import signal
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import asdict

from camoufox.sync_api import Camoufox

# Import naszego TokenStore
sys.path.insert(0, str(Path(__file__).parent))
from hybrid_token_store import TokenStore, TokenSnapshot, token_store


# Konfiguracja
ITEM_URL = "https://www.vinted.pl/items/9807925466-genesis-krypton-700"
PROFILE_DIR = r"f:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"  # kanoniczny profil
REFRESH_INTERVAL_MIN = 4  # co ile minut odświeżać
HEADLESS = True
LOCALE = "pl-PL"


class CamoufoxTokenRefresher:
    def __init__(self, 
                 item_url: str = ITEM_URL,
                 profile_dir: str = PROFILE_DIR,
                 refresh_interval_min: int = REFRESH_INTERVAL_MIN,
                 headless: bool = HEADLESS,
                 locale: str = LOCALE):
        self.item_url = item_url
        self.profile_dir = profile_dir
        self.refresh_interval = refresh_interval_min * 60  # sekundy
        self.headless = headless
        self.locale = locale
        
        self.cf = None
        self.page = None
        self.running = False
        self.refresh_count = 0
        self.last_refresh_time = 0
        self.last_error = None
        
        # Signal handlers dla graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        print(f"\n[Refresher] Received signal {signum}, shutting down...")
        self.stop()
    
    def start(self):
        """Uruchamia Camoufox i zaczyna pętlę odświeżania."""
        print(f"[Refresher] Starting Camoufox (headless={self.headless})...")
        print(f"[Refresher] Profile: {self.profile_dir}")
        print(f"[Refresher] Refresh interval: {self.refresh_interval // 60} min")
        
        try:
            self.cf = Camoufox(
                headless=self.headless,
                persistent_context=True,
                user_data_dir=self.profile_dir,
                locale=self.locale,
                # humanize=True,  # może pomóc przy DataDome
            )
            
            # Pobierz stronę (nowa lub istniejąca)
            if hasattr(self.cf, 'pages') and self.cf.pages:
                self.page = self.cf.pages[0]
            else:
                self.page = self.cf.new_page()
            
            self.running = True
            print("[Refresher] Camoufox started successfully")
            
            # Pierwsze odświeżenie natychmiast
            self._refresh_tokens()
            
            # Główna pętla
            self._run_loop()
            
        except Exception as e:
            print(f"[Refresher] Fatal error: {e}")
            token_store.add_error(f"Refresher fatal: {e}")
            self.stop()
    
    def _run_loop(self):
        """Główna pętla odświeżania."""
        while self.running:
            # Oblicz czas do następnego odświeżenia
            elapsed = time.time() - self.last_refresh_time
            sleep_time = max(0, self.refresh_interval - elapsed)
            
            if sleep_time > 0:
                print(f"[Refresher] Next refresh in {sleep_time/60:.1f} min...")
                # Sleep w małych kawałkach by reagować na stop()
                chunk = 10  # sekundy
                while sleep_time > 0 and self.running:
                    time.sleep(min(chunk, sleep_time))
                    sleep_time -= chunk
            
            if self.running:
                self._refresh_tokens()
    
    def _refresh_tokens(self):
        """Wykonuje pełny cykl: item page -> click Kup -> intercept tokeny."""
        print(f"\n[Refresher] === Refresh #{self.refresh_count + 1} ===")
        start_time = time.time()
        
        try:
            # 1. Przejdź do item page
            print(f"[Refresher] Navigating to {self.item_url}")
            self.page.goto(self.item_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)  # pozwól JS się załadować
            
            # 2. Zamknij cookie banner jeśli jest
            self._dismiss_cookie_banner()
            
            # 3. Znajdź i kliknij "Kup teraz" (isTrusted click)
            token_data = self._click_buy_and_capture()
            
            if token_data:
                # 4. Zapisz do TokenStore
                snapshot = TokenSnapshot(
                    timestamp=time.time(),
                    x_incognia_request_token=token_data["x_incognia_request_token"],
                    x_csrf_token=token_data["x_csrf_token"],
                    x_anon_id=token_data["x_anon_id"],
                    x_datadome_clientid=token_data.get("x_datadome_clientid", ""),
                    cookies=token_data["cookies"],
                    sdk_instance_id=token_data["sdk_instance_id"],
                    consume_url=token_data["consume_url"],
                    ttl_estimate_seconds=token_data.get("ttl_estimate_seconds", 300),
                    source="camoufox_refresh"
                )
                
                if token_store.update_tokens(snapshot):
                    self.refresh_count += 1
                    self.last_refresh_time = time.time()
                    elapsed = time.time() - start_time
                    print(f"[Refresher] ✅ Tokens updated (refresh #{self.refresh_count}, took {elapsed:.1f}s)")
                    print(f"  x-incognia-token: {snapshot.x_incognia_request_token[:40]}...")
                    print(f"  sdkInstanceId: {snapshot.sdk_instance_id}")
                    print(f"  cookies: {len(snapshot.cookies)} items")
                else:
                    print("[Refresher] ⚠️ Token not newer, skipped")
            else:
                print("[Refresher] ❌ Failed to capture tokens")
                token_store.add_error("Failed to capture tokens during refresh")
                
        except Exception as e:
            error_msg = f"Refresh failed: {e}"
            print(f"[Refresher] ❌ {error_msg}")
            import traceback
            traceback.print_exc()
            token_store.add_error(error_msg)
    
    def _dismiss_cookie_banner(self):
        """Zamyka OneTrust cookie banner jeśli jest widoczny."""
        try:
            # Spróbuj znaleźć przycisk "Wybierz niezbędne" lub "Zgoda na wszystkie"
            selectors = [
                'button:has-text("Wybierz niezbędne")',
                'button:has-text("Zgoda na wszystkie")',
                'button[id*="accept"]',
                'button[class*="accept"]',
                '#onetrust-accept-btn-handler',
            ]
            
            for sel in selectors:
                try:
                    btn = self.page.locator(sel).first
                    if btn.is_visible(timeout=1000):
                        btn.click(timeout=2000)
                        print(f"[Refresher] Closed cookie banner via {sel}")
                        time.sleep(0.5)
                        return
                except Exception:
                    continue
            
            # Fallback: usuń overlay przez JS
            self.page.evaluate("""
                () => {
                    const overlay = document.getElementById('onetrust-consent-sdk');
                    if (overlay) overlay.remove();
                    const filter = document.querySelector('.onetrust-pc-dark-filter');
                    if (filter) filter.remove();
                }
            """)
        except Exception as e:
            print(f"[Refresher] Cookie banner dismiss error (ignored): {e}")
    
    def _click_buy_and_capture(self) -> Optional[Dict[str, Any]]:
        """Kliknie 'Kup teraz' i przechwytuje tokeny z requestu checkout/build."""
        
        # Zmienne do przechwycenia
        captured = {
            "x_incognia_request_token": None,
            "x_csrf_token": None,
            "x_anon_id": None,
            "x_datadome_clientid": None,
            "cookies": {},
            "sdk_instance_id": None,
            "consume_url": None,
        }
        
        # Event listener na requesty
        def on_request(request):
            try:
                url = request.url
                headers = request.headers
                
                # Przechwyć checkout/build request
                if "checkout/build" in url:
                    captured["x_incognia_request_token"] = headers.get("x-incognia-request-token")
                    captured["x_csrf_token"] = headers.get("x-csrf-token")
                    captured["x_anon_id"] = headers.get("x-anon-id")
                    print(f"[Refresher] Captured checkout/build headers")
                
                # Przechwyć Incognia consume (dla sdkInstanceId i consumeUrl)
                if "j3r4zw/v1/consume" in url:
                    captured["consume_url"] = request.url.split("?")[0]
                    # sdkInstanceId jest w body - trudno pobrać z requestu, spróbuj z page.evaluate
                    
            except Exception:
                pass
        
        def on_response(response):
            try:
                # x-datadome-clientid jest w response headers
                if "checkout/build" in response.url:
                    captured["x_datadome_clientid"] = response.headers.get("x-datadome-clientid")
                    # Cookies z response
                    for cookie in response.headers.get("set-cookie", "").split(","):
                        if "=" in cookie:
                            name, val = cookie.split("=")[0].strip(), cookie.split("=")[1].split(";")[0].strip()
                            if name in ["_vinted_fr_session", "datadome", "__cf_bm", "sessionid"]:
                                captured["cookies"][name] = val
            except Exception:
                pass
        
        self.page.on("request", on_request)
        self.page.on("response", on_response)
        
        # Znajdź przycisk "Kup teraz"
        buy_button = None
        for selector in [
            'button[data-testid="item-buy-button"]',
            'button:has-text("Kup teraz")',
            'button:has-text("Kup")',
            'button:has-text("Buy now")',
            'button:has-text("Buy")',
        ]:
            try:
                el = self.page.locator(selector).first
                if el.is_visible(timeout=2000):
                    buy_button = el
                    print(f"[Refresher] Found buy button: {selector}")
                    break
            except Exception:
                continue
        
        if not buy_button:
            print("[Refresher] ❌ Buy button not found")
            return None
        
        # Kliknij (isTrusted click!)
        print("[Refresher] Clicking 'Kup teraz' (isTrusted)...")
        try:
            buy_button.click(timeout=10000)
        except Exception as e:
            print(f"[Refresher] Click error: {e}")
            return None
        
        # Czekaj na request checkout/build (max 15s)
        print("[Refresher] Waiting for checkout/build request...")
        for _ in range(30):
            time.sleep(0.5)
            if captured["x_incognia_request_token"]:
                break
        
        if not captured["x_incognia_request_token"]:
            print("[Refresher] ❌ No x-incognia-request-token captured")
            # Spróbuj pobrać z page.evaluate (fallback)
            try:
                token_from_page = self.page.evaluate("""
                    () => {
                        // Szukaj w window.__V lub w metadanych
                        if (window.__V && window.__V.incogniaToken) return window.__V.incogniaToken;
                        // Spróbuj znaleźć w localStorage/sessionStorage
                        for (let i = 0; i < localStorage.length; i++) {
                            const k = localStorage.key(i);
                            if (k && k.includes('incognia')) return localStorage.getItem(k);
                        }
                        return null;
                    }
                """)
                if token_from_page:
                    captured["x_incognia_request_token"] = token_from_page
                    print("[Refresher] Got token from page.evaluate fallback")
            except Exception:
                pass
        
        if not captured["x_incognia_request_token"]:
            return None
        
        # Pobierz sdkInstanceId i consumeUrl z page.evaluate
        try:
            sdk_data = self.page.evaluate("""
                () => {
                    const result = { sdkInstanceId: null, consumeUrl: null };
                    if (window.__V && window.__V.sdkInstanceId) {
                        result.sdkInstanceId = window.__V.sdkInstanceId;
                    }
                    if (window.__V && window.__V.consumeUrl) {
                        result.consumeUrl = window.__V.consumeUrl;
                    }
                    // Fallback: szukaj w localStorage
                    if (!result.sdkInstanceId) {
                        for (let i = 0; i < localStorage.length; i++) {
                            const k = localStorage.key(i);
                            if (k && k.includes('sdkInstanceId')) {
                                result.sdkInstanceId = localStorage.getItem(k);
                                break;
                            }
                        }
                    }
                    return result;
                }
            """)
            if sdk_data:
                captured["sdk_instance_id"] = sdk_data.get("sdkInstanceId")
                captured["consume_url"] = sdk_data.get("consumeUrl") or captured["consume_url"]
        except Exception:
            pass
        
        # Pobierz cookies z kontekstu przeglądarki
        try:
            cookies = self.page.context.cookies()
            for c in cookies:
                if c["name"] in ["_vinted_fr_session", "datadome", "__cf_bm", "sessionid", "csrf_token"]:
                    captured["cookies"][c["name"]] = c["value"]
        except Exception:
            pass
        
        # Wypełnij brakujące pola z TokenStore jeśli mamy stare
        old = token_store.get_tokens()
        if old:
            captured["x_csrf_token"] = captured["x_csrf_token"] or old.x_csrf_token
            captured["x_anon_id"] = captured["x_anon_id"] or old.x_anon_id
            captured["sdk_instance_id"] = captured["sdk_instance_id"] or old.sdk_instance_id
            captured["consume_url"] = captured["consume_url"] or old.consume_url
            # Merge cookies
            for k, v in old.cookies.items():
                captured["cookies"].setdefault(k, v)
        
        print(f"[Refresher] Captured: incognia_token={'YES' if captured['x_incognia_request_token'] else 'NO'}, "
              f"csrf={'YES' if captured['x_csrf_token'] else 'NO'}, "
              f"sdkInstanceId={'YES' if captured['sdk_instance_id'] else 'NO'}")
        
        return captured
    
    def stop(self):
        """Zatrzymuje refresher i zamyka Camoufox."""
        print("[Refresher] Stopping...")
        self.running = False
        
        if self.cf:
            try:
                self.cf.close()
                print("[Refresher] Camoufox closed")
            except Exception as e:
                print(f"[Refresher] Error closing Camoufox: {e}")


def main():
    """Uruchamia refresher jako daemon."""
    print("=" * 60)
    print("Camoufox Token Refresher - Hybrid Mode")
    print("=" * 60)
    
    refresher = CamoufoxTokenRefresher()
    try:
        refresher.start()
    except KeyboardInterrupt:
        print("\n[Refresher] Interrupted by user")
    finally:
        refresher.stop()


if __name__ == "__main__":
    main()