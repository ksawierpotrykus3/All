# coding: utf-8
"""_reharvest_datadome_135.py — generuje swieze cookie `datadome` pod TLS Firefox 135.

Konteks: obnizylismy Camoufox do 135.0.1-beta.24, ktory 1:1 matchuje wbudowany
profil `firefox135` curl_cffi (ja3/ja4/peet/cert_comp [zlib,brotli,zstd]).

Problem: cookie `datadome` w cookies_profil.json pochodzi z TLS FF152 (DataDome
odciska w nim fingerprint ClientHello). Przy uzyciu firefox135 w curl_cffi daje 403.

Rozwiazanie: zalogowana sesja (access_token_web/refresh_token_web/_vinted_fr_session)
jest niezalezna od TLS i przenosna. Wstrzykujemy ja do profilu 135 (BEZ datadome),
ladujemy publiczne strony vinted.pl -> frontend generuje NOWE datadome odcisniete
pod TLS FF135 -> eksportujemy caly zestaw do cookies_profil.json.

Bezpieczenstwo: tylko GET-y publiczne (home/catalog/item), zero automatyzacji
platnosci/rezerwacji.
"""
import json
import time
from pathlib import Path

from camoufox import Camoufox

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR / "profil_firefox_135"
COOKIES_IN = BASE_DIR / "cookies_profil.json"      # zrodlo zalogowanej sesji (152)
COOKIES_OUT = BASE_DIR / "cookies_profil.json"     # nadpisujemy swiezym zestawem
TIMEOUT_S = 90

# Publiczne sciezki wywolujace skrypt DataDome (BEZ akcji transakcyjnych).
URLS = [
    "https://www.vinted.pl/",
    "https://www.vinted.pl/catalog",
    "https://www.vinted.pl/catalog/clothes",
]

# Strony itemu wyzwalaja DataDome najsilniej (build_probe / reset_datadome_cookie
# ustawialy cookie wlasnie tam). Pobieramy zywy item z katalogu.
CATALOG_API = (
    "https://www.vinted.pl/api/v2/catalog/items"
    "?catalog_ids%5B%5D=44&price_to=50&order=newest_first&page=1&per_page=5&currency=PLN"
)


def _is_logged_in(page) -> dict | None:
    try:
        data = page.evaluate(
            """async () => {
                const r = await fetch('/api/v2/users/current', {
                    headers: {'Accept': 'application/json'}
                });
                return {status: r.status, body: await r.text()};
            }"""
        )
        if data.get("status") != 200:
            return None
        body = json.loads(data["body"])
        login = body.get("user", {}).get("login") or body.get("login")
        uid = body.get("user", {}).get("id") or body.get("id")
        if login and uid:
            return {"login": login, "id": uid}
    except Exception as e:  # noqa: BLE001
        print(f"BLAD sprawdzania logowania: {e}")
    return None


def _parse_cookies(raw) -> list:
    out = []
    for c in raw:
        out.append({
            "name": c.get("name", ""),
            "value": c.get("value", ""),
            "domain": c.get("domain", ""),
            "path": c.get("path", "/"),
            "expires": c.get("expires", -1),
            "httpOnly": c.get("httpOnly", False),
            "secure": c.get("secure", False),
            "sameSite": c.get("sameSite", "Lax"),
        })
    return out


def main() -> None:
    # 0) Zrodlo zalogowanej sesji: cookies_profil.json (z FF152), bez datadome.
    if not COOKIES_IN.exists():
        print("BRAK cookies_profil.json — najpierw zaloguj sesje (harvest_cookies_firefox.py).")
        return

    src = json.loads(COOKIES_IN.read_text(encoding="utf-8"))
    old_datadome = next((c["value"] for c in src if c.get("name") == "datadome"), "")
    seed = [c for c in src if c.get("name") != "datadome"]
    print(f"Seed: {len(seed)} cookies (bez datadome), stary datadome={old_datadome[:40] or '(BRAK)'}...")

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    with Camoufox(
        persistent_context=True,
        headless=True,
        user_data_dir=str(PROFILE_DIR),
        os="windows",
        fingerprint_preset=True,
        humanize=True,
    ) as ctx:
        # 1) Wstrzyknij zalogowana sesje (bez datadome).
        ctx.clear_cookies()
        ctx.add_cookies(seed)

        # 2) Laduj publiczne strony az DataDome ustawi swieze datadome.
        page = ctx.new_page()
        got_datadome = False

        def _check_datadome():
            ck = ctx.cookies("https://www.vinted.pl/")
            return any(c.get("name") == "datadome" for c in ck)

        # 2a) Home + katalog.
        for u in URLS:
            if got_datadome:
                break
            try:
                page.goto(u, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(8000)  # czas na skrypt DataDome
            except Exception as e:  # noqa: BLE001
                print(f"BLAD goto {u}: {e}")
            got_datadome = _check_datadome()
            if got_datadome:
                print(f"datadome ustawiony na: {u}")

        # 2b) Strony itemow — DataDome setuje cookie najsilniej wlasnie tam.
        if not got_datadome:
            catalog_js = (
                "async () => {"
                "  const r = await fetch('" + CATALOG_API + "', {headers: {'Accept': 'application/json'}});"
                "  const j = await r.json();"
                "  return (j.items || []).filter(it => it && it.id).map(it => ({id: it.id}));"
                "}"
            )
            try:
                items = page.evaluate(catalog_js)
            except Exception as e:  # noqa: BLE001
                print(f"BLAD pobierania katalogu: {e}")
                items = []

            for it in items[:5]:
                if got_datadome:
                    break
                item_url = f"https://www.vinted.pl/items/{it['id']}-probe"
                try:
                    page.goto(item_url, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(8000)
                except Exception as e:  # noqa: BLE001
                    print(f"BLAD goto item {it['id']}: {e}")
                got_datadome = _check_datadome()
                if got_datadome:
                    print(f"datadome ustawiony na itemie {it['id']}")

        if not got_datadome:
            print("UWAGA: nie wygenerowano datadome na publicznych stronach.")

        # 3) Potwierdz zalogowana sesje (tokeny przeniesione OK).
        start = time.time()
        account = None
        while time.time() - start < TIMEOUT_S:
            account = _is_logged_in(page)
            if account:
                break
            time.sleep(2)
        if not account:
            print("NIE wykryto zalogowanej sesji po wstrzyknieciu tokenow (wyglada, ze tokeny wygasly).")
            print("Wymagane reczne zalogowanie: harvest_cookies_firefox.py")
            return

        # 4) Eksport swiezego, spójnego zestawu (nowe datadome pod TLS 135).
        cookies = _parse_cookies(ctx.cookies())
        new_datadome = next((c["value"] for c in cookies if c.get("name") == "datadome"), "")
        COOKIES_OUT.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"Zalogowano: {account['login']} (id {account['id']})")
        print(f"Zapisano {len(cookies)} cookies do: {COOKIES_OUT}")
        print(f"datadome STARY : {old_datadome[:40] or '(BRAK)'}...")
        print(f"datadome NOWY  : {new_datadome[:40] or '(BRAK)'}...")
        print(f"datadome ZMIENIONY: {bool(new_datadome) and new_datadome != old_datadome}")


if __name__ == "__main__":
    main()