# coding: utf-8
"""reset_datadome_cookie.py — resetuje cookie DataDome w profilu Camoufox.

Blokada po rotacji fingerprintow (speed_opt_probe3) siedzi w cookie `datadome`
(DataDome odciska fingerprint requesta w tym cookie; rozne fingerprinty na tym
samym cookie = blokada warstwy transakcyjnej: build/payment 403).

Reset: usuwamy TYLKO cookie `datadome` (sesja zalogowana zostaje), ladujemy
vinted.pl (frontend generuje nowy, czysty cookie datadome) i eksportujemy
swieze cookies do cookies_profil.json (format uzywany przez testy curl_cffi).

Uzycie: python reset_datadome_cookie.py
"""
import json
import time
from pathlib import Path

from camoufox import Camoufox

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR / "profil_firefox_135"
COOKIES_OUT = BASE_DIR / "cookies_profil.json"
TIMEOUT_S = 90


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


def main() -> None:
    # 0) Backup aktualnych cookies do porownania datadome (stare vs nowe).
    old_path = BASE_DIR / "cookies_profil.json.bak_datadome"
    if COOKIES_OUT.exists():
        old_path.write_bytes(COOKIES_OUT.read_bytes())

    with Camoufox(
        persistent_context=True,
        headless=True,
        user_data_dir=str(PROFILE_DIR),
        os="windows",
        fingerprint_preset=True,
        humanize=True,
        block_webgl=True,
    ) as ctx:
        # 1) Usun stare (mozliwie skazone) cookie datadome - sesja zostaje.
        ctx.clear_cookies(name="datadome")
        print("usunieto cookie datadome", flush=True)

        # 2) Laduj strone - frontend generuje nowy cookie datadome.
        page = ctx.new_page()
        page.goto("https://www.vinted.pl/", wait_until="domcontentloaded", timeout=60000)

        # 2b) Datadome setuje cookie asynchronicznie po wykonaniu JS.
        # Przechodzimy przez publiczne strony (home -> katalog -> item), aby
        # wymusic wykonanie skryptu DataDome. Tylko GET-y publiczne (bezpieczne).
        urls = [
            "https://www.vinted.pl/",
            "https://www.vinted.pl/catalog",
            "https://www.vinted.pl/catalog/clothes",
            "https://www.vinted.pl/items/9807925466-genesis-krypton-700",
        ]
        got_datadome = False
        for u in urls:
            if not got_datadome:
                try:
                    page.goto(u, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(8000)  # czas na skrypt DataDome
                except Exception as e:  # noqa: BLE001
                    print(f"BLAD goto {u}: {e}", flush=True)
            ck = ctx.cookies("https://www.vinted.pl/")
            got_datadome = any(c.get("name") == "datadome" for c in ck)
            if got_datadome:
                print(f"datadome ustawiony na: {u}", flush=True)
                break
        if not got_datadome:
            print("UWAGA: nie wygenerowano datadome cookie na publicznych stronach.", flush=True)

        # 3) Czekaj na potwierdzenie zalogowanej sesji (auto-refresh tokenu).
        start = time.time()
        account = None
        while time.time() - start < TIMEOUT_S:
            account = _is_logged_in(page)
            if account:
                break
            time.sleep(2)
        if not account:
            print("NIE wykryto zalogowanej sesji - abort (wymagany reczny login).", flush=True)
            return

        # 4) Eksportuj swieze cookies (ten sam format co export_cookies_json.py).
        raw = ctx.cookies()
        cookies = []
        datadome_new = None
        for c in raw:
            entry = {
                "name": c.get("name", ""),
                "value": c.get("value", ""),
                "domain": c.get("domain", ""),
                "path": c.get("path", "/"),
                "expires": c.get("expires", -1),
                "httpOnly": c.get("httpOnly", False),
                "secure": c.get("secure", False),
                "sameSite": c.get("sameSite", "Lax"),
            }
            if c.get("name") == "datadome":
                datadome_new = c.get("value", "")
            cookies.append(entry)

        COOKIES_OUT.write_text(
            json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # 5) Weryfikacja: nowy datadome musi istniec i byc inny niz stary.
        old = None
        # porownanie wartosci: wczytaj poprzedni jesli zapisany
        if old_path.exists():
            try:
                old_list = json.loads(old_path.read_text(encoding="utf-8"))
                for c in old_list:
                    if c.get("name") == "datadome":
                        old = c.get("value", "")
            except Exception:  # noqa: BLE001
                pass

        prefix_new = datadome_new[:40] if datadome_new else "(BRAK)"
        prefix_old = old[:40] if old else "(BRAK)"
        changed = datadome_new is not None and datadome_new != old
        print(f"Zalogowano: {account['login']} (id {account['id']})", flush=True)
        print(f"Zapisano {len(cookies)} cookies do: {COOKIES_OUT}", flush=True)
        print(f"datadome STARY  : {prefix_old}...", flush=True)
        print(f"datadome NOWY   : {prefix_new}...", flush=True)
        print(f"datadome ZMIENIONY: {changed}", flush=True)


if __name__ == "__main__":
    main()
