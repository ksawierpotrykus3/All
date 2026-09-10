"""Automatyczny headless test i auto-refresh sesji OLX z trwałego profilu (jak Vinted).

Sprawdza czy profil 'profiles/olx_profile' posiada wazna sesje:
1. Odczytuje cookies z profilu.
2. Jesli access_token wygasa, odswieza go w tle przez headless Chromium.
3. Weryfikuje zywotnosc sesji na API GET /api/v1/users/me/ (kod 200).
"""
import base64
import json
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from curl_cffi import requests as creq

BASE = Path(__file__).resolve().parent.parent.parent
PROFILE_DIR = BASE / "profiles" / "olx_profile"
DANE_DIR = BASE / "gemini" / "dane"


def parse_jwt(token: str) -> dict:
    try:
        parts = token.split(".")
        if len(parts) >= 2:
            pad = parts[1] + "=" * (-len(parts[1]) % 4)
            return json.loads(base64.b64decode(pad).decode("utf-8"))
    except Exception:
        pass
    return {}


def format_cookies_netscape(cookies: list) -> str:
    lines = [
        "# Netscape HTTP Cookie File",
        "# Auto-refreshed by test_session_refresh.py",
        "",
    ]
    for c in cookies:
        domain = c.get("domain", "")
        flag = "TRUE" if domain.startswith(".") else "FALSE"
        path = c.get("path", "/")
        secure = "TRUE" if c.get("secure", False) else "FALSE"
        expires = int(c.get("expires", 0))
        if expires <= 0:
            expires = int(time.time()) + 86400 * 30
        name = c.get("name", "")
        value = c.get("value", "")
        lines.append(f"{domain}\t{flag}\t{path}\t{secure}\t{expires}\t{name}\t{value}")
    return "\n".join(lines) + "\n"


def refresh_session_headless() -> dict:
    """Odpala Chromium w tle, odwiedza OLX i zbiera swiezy token po silent auth."""
    print("[*] Uruchamiam headless refresh z trwalego profilu...")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=True,
            locale="pl-PL",
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://www.olx.pl/", wait_until="domcontentloaded", timeout=45000)
        # Czekamy na silent auth iframe do login.olx.pl
        page.wait_for_timeout(4000)

        all_cookies = ctx.cookies()
        ctx.storage_state(path=str(DANE_DIR / "storage_state.json"))
        ctx.close()

    cookie_dict = {c["name"]: c["value"] for c in all_cookies}
    tok = cookie_dict.get("access_token", "")
    
    # Zapisz zaktualizowane cookies.txt
    netscape = format_cookies_netscape(all_cookies)
    (BASE / "dane" / "cookies.txt").write_text(netscape, encoding="utf-8")
    (DANE_DIR / "cookies.txt").write_text(netscape, encoding="utf-8")
    (DANE_DIR / "cookies.json").write_text(json.dumps(all_cookies, indent=2), encoding="utf-8")

    return {"token": tok, "cookies": all_cookies, "dict": cookie_dict}


def main():
    print("=" * 60)
    print("=== TEST I REFRESH SESJI OLX (Headless) ===")
    print("=" * 60)

    if not PROFILE_DIR.exists():
        print(f"[!] Blad: Katalog profilu {PROFILE_DIR} nie istnieje.")
        print("[!] Uruchom najpierw ZALOGUJ_SIE_OLX.bat, aby zalogowac sie jednorazowo.")
        sys.exit(1)

    # Odswiez sesje
    session = refresh_session_headless()
    token = session["token"]

    if not token:
        print("[!] BLAD: Profil nie posiada tokena access_token. Wymagane zalogowanie (ZALOGUJ_SIE_OLX.bat).")
        sys.exit(1)

    payload = parse_jwt(token)
    exp = payload.get("exp", 0)
    cur = int(time.time())
    rem = exp - cur

    print(f"[+] Odczytano access_token (waznosc: jeszcze {rem} sekund / {rem//60} min)")
    print(f"    Email: {payload.get('email') or payload.get('custom:idp_last_email')}")
    print(f"    User UUID: {payload.get('sub')}")

    # Deterministyczny test API
    print("\n[*] Sprawdzam autoryzacje na API: GET /api/v1/users/me/...")
    r = creq.get(
        "https://www.olx.pl/api/v1/users/me/",
        headers={"Authorization": f"Bearer {token}"},
        impersonate="chrome124",
        timeout=10,
    )
    print(f"[*] Kod HTTP: {r.status_code}")
    if r.status_code == 200:
        print(f"[OK] SUKCES! Sesja aktywna i w pelni dziala.")
        out_file = DANE_DIR / "session_verified.json"
        out_file.write_text(json.dumps({"status": 200, "user": r.json()}, indent=2), encoding="utf-8")
        print(f"[+] Wynik zapisano do {out_file}")
    else:
        print(f"[FAIL] BLAD: Otrzymano kod {r.status_code}: {r.text[:300]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
