# coding: utf-8
"""_reharvest_datadome_135_headed.py — genera swieze `datadome` przez headed przegladanie.

Przyczyna braku datadome w headless: DataDome wydaje clearance cookie tylko przy
realnym (headed) przegladaniu z humanize=True — pelny fingerprint JS (canvas,
audio, ad_blocker_detected). Headless Camoufox czesciowo blokuje te sygnaly.

Profil 135 ma juz zalogowana sesje (access_token_web/refresh_token_web/
_vinted_fr_session w cookies.sqlite). Wystarczy headed przejsc przez publiczne
strony (home -> katalog -> realny item), aby DataDome ustawil datadome.

Bezpieczenstwo: TYLKO GET-y publiczne, zero akcji transakcyjnych/rezerwacji.
"""
import json
import time
from pathlib import Path

from camoufox import Camoufox

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR / "profil_firefox_135"
COOKIES_OUT = BASE_DIR / "cookies_profil.json"
TIMEOUT_S = 90

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


def _check_datadome(ctx) -> bool:
    ck = ctx.cookies("https://www.vinted.pl/")
    return any(c.get("name") == "datadome" for c in ck)


def main() -> None:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    with Camoufox(
        persistent_context=True,
        headless=False,          # KLUCZ: headed — DataDome wydaje clearance tylko tu
        user_data_dir=str(PROFILE_DIR),
        os="windows",
        fingerprint_preset=True,
        humanize=True,           # pelny fingerprint JS
        webgl_config=("Google Inc. (AMD)", "ANGLE (AMD, Radeon R9 200 Series Direct3D11 vs_5_0 ps_5_0)"),
    ) as ctx:
        page = ctx.new_page()

        # Potwierdz zalogowana sesje (tokeny przeniesione z profilu 152).
        start = time.time()
        account = None
        while time.time() - start < TIMEOUT_S:
            account = _is_logged_in(page)
            if account:
                break
            time.sleep(2)
        if not account:
            print("NIE wykryto zalogowanej sesji — tokeny wygasly lub brak. "
                  "Wymagane reczne zalogowanie: harvest_cookies_firefox.py")
            return
        print(f"Zalogowano: {account['login']} (id {account['id']})")

        # Przejdz przez publiczne strony, aby DataDome ustawil datadome.
        page.goto("https://www.vinted.pl/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)
        print(f"home: datadome={_check_datadome(ctx)}")

        # Pobierz realne itemy.
        catalog_js = (
            "async () => {"
            "  const r = await fetch('" + CATALOG_API + "', {headers: {'Accept': 'application/json'}});"
            "  const j = await r.json();"
            "  return (j.items | []).filter(it => it && it.id).map(it => ({id: it.id}));"
            "}"
        )
        try:
            items = page.evaluate(catalog_js)
        except Exception as e:  # noqa: BLE001
            print(f"BLAD pobierania katalogu: {e}")
            items = []

        got = False
        for it in items[:5]:
            if got:
                break
            try:
                page.goto(f"https://www.vinted.pl/items/{it['id']}-probe",
                          wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(6000)
            except Exception as e:  # noqa: BLE001
                print(f"BLAD goto item {it['id']}: {e}")
            got = _check_datadome(ctx)
            print(f"item {it['id']}: datadome={got}")

        if not got:
            print("UWAGA: nadal nie wygenerowano datadome.")
        else:
            print("datadome ustawiony!")

        # Eksport swiezego zestawu cookies.
        raw = ctx.cookies()
        cookies = []
        for c in raw:
            cookies.append({
                "name": c.get("name", ""),
                "value": c.get("value", ""),
                "domain": c.get("domain", ""),
                "path": c.get("path", "/"),
                "expires": c.get("expires", -1),
                "httpOnly": c.get("httpOnly", False),
                "secure": c.get("secure", False),
                "sameSite": c.get("sameSite", "Lax"),
            })
        COOKIES_OUT.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
        dd = next((c["value"] for c in cookies if c.get("name") == "datadome"), "")
        print(f"Zapisano {len(cookies)} cookies do: {COOKIES_OUT}")
        print(f"datadome NOWY: {dd[:40] if dd else '(BRAK)'}...")


if __name__ == "__main__":
    main()