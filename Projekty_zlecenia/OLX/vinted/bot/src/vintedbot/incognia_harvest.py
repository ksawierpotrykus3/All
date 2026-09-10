"""Przechwycenie x-incognia-request-token (JWE) z sesji Camoufox.

Token Incognia powstaje tylko w prawdziwej przeglądarce po kliknięciu
"Kup teraz" (lazy-load SDK + trusted event). Zwracamy przechwycony token,
żeby curl_cffi mogł go użyć w checkout/build.
"""
from __future__ import annotations

from camoufox import Camoufox

from .config import profile_lock
from .refresh import WEBGL_CONFIG
from .slider_solver import rozwiaz_slider


def przechwyc_token_incognia(item_id: int, profil: str, timeout_s: int = 60) -> dict:
    """Otwiera item w Camoufox, klika 'Kup teraz', przechwytuje token z builda.

    Zwraca dict z kluczami:
      - token: przechwycony x-incognia-request-token (JWE) lub None
      - status_build: HTTP status builda (jeśli poszedł)
      - segmenty: liczba segmentow tokena (5 = JWE)
    """
    wynik = {"token": None, "status_build": None, "segmenty": 0, "cookies": {},
             "build_body": None, "build_resp": None, "put_body": None, "put_resp": None}

    def on_request(req):
        h = req.headers or {}
        if "x-incognia-request-token" in h:
            wynik["token"] = h["x-incognia-request-token"]
            wynik["segmenty"] = len(wynik["token"].split("."))
        if "checkout/build" in req.url:
            try:
                wynik["build_body"] = req.post_data
            except Exception:
                pass
        # PUT /purchases/{id}/checkout (metoda płatności) — pełny payload.
        if req.method == "PUT" and "/purchases/" in req.url and req.url.endswith("/checkout"):
            try:
                wynik["put_body"] = req.post_data
            except Exception:
                pass

    def on_response(resp):
        if "checkout/build" in resp.url:
            wynik["status_build"] = resp.status
            try:
                wynik["build_resp"] = resp.json()
            except Exception:
                try:
                    wynik["build_resp"] = resp.text()[:2000]
                except Exception:
                    pass
        if resp.request.method == "PUT" and "/purchases/" in resp.url and resp.url.endswith("/checkout"):
            try:
                wynik["put_resp"] = {"status": resp.status, "body": resp.text()[:2000]}
            except Exception:
                pass

    with profile_lock(profil), Camoufox(
        persistent_context=True,
        headless=True,
        user_data_dir=profil,
        os="windows",
        fingerprint_preset=True,
        humanize=True,
        webgl_config=WEBGL_CONFIG,
    ) as ctx:
        page = ctx.new_page()
        page.on("request", on_request)
        page.on("response", on_response)
        page.goto(f"https://www.vinted.pl/items/{item_id}", wait_until="domcontentloaded", timeout=60000)
        # Wyczysc baner cookie, zeby klikniecie bylo mozliwe.
        try:
            page.evaluate(
                "() => { const b=document.querySelector('#onetrust-accept-btn-handler'); if(b) b.click();"
                " const f=document.querySelector('.onetrust-pc-dark-filter'); if(f) f.remove();"
                " const c=document.querySelector('#onetrust-consent-sdk'); if(c) c.remove(); }"
            )
        except Exception:
            pass
        def _klik():
            try:
                page.get_by_test_id("item-buy-button").click(timeout=timeout_s * 1000)
            except Exception:
                try:
                    page.click("button:has-text('Kup teraz')", timeout=timeout_s * 1000)
                except Exception:
                    pass

        _klik()
        # Czekaj na build. Jeśli challenge (iframe captcha) -> rozwiąż slider i ponów.
        try:
            page.wait_for_timeout(4000)
        except Exception:
            pass

        if wynik.get("status_build") == 403:
            wynik["slider_proba"] = True
            if rozwiaz_slider(page, proby=3):
                wynik["slider_solved"] = True
                # Po rozwiązaniu: reload + ponowne kliknięcie.
                try:
                    page.reload(wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(3000)
                except Exception:
                    pass
                _klik()
                try:
                    page.wait_for_timeout(8000)
                except Exception:
                    pass
            else:
                wynik["slider_solved"] = False

        # Czekaj na build + nawigację do checkout + ewentualny PUT payment_method.
        try:
            page.wait_for_timeout(8000)
        except Exception:
            pass
        # Świeże cookies po kliknięciu (datadome jest rotowane przez build).
        try:
            raw = ctx.cookies()
            wynik["cookies"] = {c.get("name", ""): c.get("value", "") for c in raw if c.get("name")}
        except Exception:
            pass
    return wynik
