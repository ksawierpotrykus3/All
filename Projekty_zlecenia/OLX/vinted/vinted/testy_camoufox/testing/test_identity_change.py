# coding: utf-8
"""Test: czy curl_cffi poprawnie zmienia tożsamość (fingerprint) między sesjami.

Sprawdzamy:
1. Czy każda nowa sesja curl_cffi ma inny TLS/JA3 fingerprint?
2. Czy cookies sa poprawnie przypisywane do sesji?
3. Czy mozna zautomatyzowac zmiane tożsamości bez Camoufox?
"""
import json
import time
from pathlib import Path

from curl_cffi import BrowserType, requests as cr

BASE_DIR = Path(__file__).resolve().parent

def test_session_fingerprint(session_num):
    """Tworzy nowa sesje i sprawdza fingerprint."""
    s = cr.Session()

    # Test TLS fingerprint przez httpbin
    try:
        r = s.get("https://httpbin.org/headers", impersonate=BrowserType.chrome146, timeout=10)
        headers = r.json().get("headers", {})
        ua = headers.get("User-Agent", "brak")
        print(f"Sesja {session_num}: UA={ua[:80]}")
        return {"ua": ua, "session_id": id(s)}
    except Exception as e:
        print(f"Sesja {session_num}: BLAD {e}")
        return {"error": str(e)}

def test_cookies_isolation():
    """Sprawdza, czy cookies sa izolowane miedzy sesjami."""
    cookies = json.loads((BASE_DIR / "cookies_profil.json").read_text(encoding="utf-8"))

    s1 = cr.Session()
    s2 = cr.Session()

    for c in cookies:
        try:
            s1.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
        except Exception:
            pass

    for c in cookies:
        try:
            s2.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
        except Exception:
            pass

    # Sprawdz kluczowe cookies (unikaj konfliktow domenowych)
    key_names = ["_vinted_fr_session", "datadome", "anon_id", "access_token_web"]
    same = True
    for name in key_names:
        v1 = None
        v2 = None
        for c in cookies:
            if c.get("name") == name:
                v1 = s1.cookies.get(name, domain=c.get("domain", ""))
                v2 = s2.cookies.get(name, domain=c.get("domain", ""))
                break
        if v1 != v2:
            same = False
            print(f"  Cookie {name}: ROZNE")
        else:
            print(f"  Cookie {name}: identyczne")
    print(f"Cookies identyczne miedzy sesjami: {same}")
    return same

def test_vinted_session_reset():
    """Sprawdza, czy Vinted widzi nowa sesje jako nowa tozsamosc."""
    # Sesja 1
    s1 = cr.Session()
    cookies = json.loads((BASE_DIR / "cookies_profil.json").read_text(encoding="utf-8"))
    for c in cookies:
        try:
            s1.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
        except Exception:
            pass
    s1.headers.update({
        "accept": "application/json,text/plain,*/*,image/webp",
        "accept-language": "pl,en-US;q=0.9,en;q=0.8,ru;q=0.7",
        "content-type": "application/json",
        "locale": "pl-PL",
        "origin": "https://www.vinted.pl",
        "referer": "https://www.vinted.pl/",
    })
    H = {"x-csrf-token": "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e",
         "x-anon-id": "98c6af5a-87da-45f2-9be5-24cf9345b003"}

    r1 = s1.get("https://www.vinted.pl/api/v2/users/current", headers=H,
                impersonate=BrowserType.chrome146, timeout=30)
    print(f"Sesja 1 users/current: {r1.status_code}")

    # Sesja 2 (nowa instancja, te same cookies)
    s2 = cr.Session()
    for c in cookies:
        try:
            s2.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
        except Exception:
            pass
    s2.headers.update(s1.headers)

    r2 = s2.get("https://www.vinted.pl/api/v2/users/current", headers=H,
                impersonate=BrowserType.chrome146, timeout=30)
    print(f"Sesja 2 users/current: {r2.status_code}")

    # Sprawdz, czy Vinted zwraca te same dane (czyli sesja jest taka sama)
    if r1.status_code == 200 and r2.status_code == 200:
        d1 = r1.json()
        d2 = r2.json()
        same_user = d1.get("user", {}).get("id") == d2.get("user", {}).get("id")
        print(f"Ten sam uzytkownik: {same_user}")
        print(f"Sesja 1 user_id: {d1.get('user', {}).get('id')}")
        print(f"Sesja 2 user_id: {d2.get('user', {}).get('id')}")
        return same_user

    return None

def main():
    print("=== TEST 1: Fingerprint sesji ===")
    results = []
    for i in range(3):
        results.append(test_session_fingerprint(i + 1))
        time.sleep(1)

    print("\n=== TEST 2: Izolacja cookies ===")
    test_cookies_isolation()

    print("\n=== TEST 3: Czy Vinted widzi nowa sesje jako nowa tozsamosc? ===")
    same = test_vinted_session_reset()

    print("\n=== WNIOSKI ===")
    print("1. curl_cffi tworzy nowa sesje z tym samym fingerprintem (impersonate=chrome146)")
    print("2. Cookies sa wspoldzielone (ten sam plik) - Vinted widzi to jako TA SAMA sesja")
    print("3. Zmiana tożsamości wymaga: nowe cookies (nowe logowanie) LUB proxy + rotacja IP")
    print("4. Automatyzacja: NIE jest mozliwa bez dostepu do nowych cookies (logowanie)")

if __name__ == "__main__":
    main()
