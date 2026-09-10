"""Interaktywne logowanie do OLX przez Playwright z trwałym profilem (jak Vinted).

Uruchamia widoczne okno Chromium z dedykowanym profilem na dysku (profiles/olx_profile).
Uzytkownik loguje sie raz (Google, Apple, email/haslo).
Gdy skrypt wykryje aktywna sesje (cookie access_token):
1. Zapisuje cookies i storage_state.
2. Wykonuje test API GET /api/v1/users/me/.
3. Zamyka okno i potwierdza gotowosc sesji.
"""
import base64
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from curl_cffi import requests as creq

BASE = Path(__file__).resolve().parent.parent.parent
PROFILE_DIR = BASE / "profiles" / "olx_profile"
DANE_DIR = BASE / "gemini" / "dane"
DANE_DIR.mkdir(parents=True, exist_ok=True)
PROFILE_DIR.mkdir(parents=True, exist_ok=True)


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
        "# Generated automatically by gemini/skrypty/login_headed.py",
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


def main():
    print("=" * 60)
    print("=== LOGOWANIE DO OLX (Tryb Trwalego Profilu Playwright) ===")
    print("=" * 60)
    print(f"[*] Katalog profilu: {PROFILE_DIR}")
    print("[*] Otwieram przegladarke...")
    print("[*] Jesli nie jestes zalogowany, zaloguj sie na swoje konto.")
    print("[*] Skrypt samoczynnie wykryje zalogowanie i zapisze sesje.\n")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1280, "height": 850},
            locale="pl-PL",
            args=["--disable-blink-features=AutomationControlled"],
        )

        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://www.olx.pl/", wait_until="domcontentloaded", timeout=60000)

        print("[*] Czekam na zalogowanie (maksymalnie 300 sekund)...")

        token_found = False
        active_token = ""
        user_email = ""

        start_t = time.time()
        while time.time() - start_t < 300:
            all_cookies = ctx.cookies()
            cookie_dict = {c["name"]: c["value"] for c in all_cookies}

            if "access_token" in cookie_dict:
                tok = cookie_dict["access_token"]
                payload = parse_jwt(tok)
                exp = payload.get("exp", 0)
                cur = int(time.time())

                if exp > cur + 60:
                    token_found = True
                    active_token = tok
                    user_email = payload.get("email") or payload.get("custom:idp_last_email") or "Konto OLX"
                    print(f"\n[+] WYKRYTO AKTYWNY ACCESS_TOKEN!")
                    print(f"    Uzytkownik: {user_email}")
                    print(f"    Wazny jeszcze przez: {exp - cur} sekund")
                    break

            time.sleep(2)

        if not token_found:
            print("\n[!] Timeout lub nie wykryto logowania. Zamknij okno i sprobuj ponownie.")
            ctx.close()
            return

        print("\n[*] Zapisywanie pelnego stanu sesji do plikow...")
        # 1. Zapis storage_state
        state_file = DANE_DIR / "storage_state.json"
        ctx.storage_state(path=str(state_file))
        print(f"[+] Zapisano: {state_file}")

        # 2. Zapis cookies.txt w formacie Netscape
        netscape_txt = format_cookies_netscape(all_cookies)
        cookies_txt_path = BASE / "dane" / "cookies.txt"
        cookies_txt_path.write_text(netscape_txt, encoding="utf-8")
        (DANE_DIR / "cookies.txt").write_text(netscape_txt, encoding="utf-8")
        print(f"[+] Zaktualizowano: {cookies_txt_path}")

        # 3. Zapis cookies w formacie JSON
        (DANE_DIR / "cookies.json").write_text(json.dumps(all_cookies, indent=2), encoding="utf-8")

        # 4. Weryfikacja deterministyczna API /users/me/
        print("\n[*] Deterministyczny test API /api/v1/users/me/ przez curl_cffi...")
        try:
            r = creq.get(
                "https://www.olx.pl/api/v1/users/me/",
                headers={"Authorization": f"Bearer {active_token}"},
                impersonate="chrome124",
                timeout=10,
            )
            print(f"[+] Kod odpowiedzi API: {r.status_code}")
            if r.status_code == 200:
                print(f"[+] DANE PROFILU ZWERYFIKOWANE: {r.text[:200]}")
                (DANE_DIR / "test_users_me_success.json").write_text(r.text, encoding="utf-8")
            else:
                print(f"[!] Nieoczekiwany kod API: {r.status_code}, tresc: {r.text[:200]}")
        except Exception as e:
            print(f"[!] Blad testu API: {e}")

        print("\n" + "=" * 60)
        print("[OK] SUKCES: Profil przegladarki zapisany pomyslnie!")
        print("Mozesz teraz uruchamiac testy checkoutu bez logowania!")
        print("=" * 60)

        # Czekamy 2 sekundy i zamykamy okno
        time.sleep(2)
        ctx.close()


if __name__ == "__main__":
    main()
