# coding: utf-8
"""Pomiar JA3/JA4/Akamai fingerprintu Firefoksa 152 z Camoufox.

Bezpieczenstwo: jedyny request wychodzi do tls.peet.ws (publiczny serwis
testowania TLS fingerprintingu), NIE do Vinted. Zero logowania, zero cookies,
zero endpointow transakcyjnych. Cel wylacznie naukowy: uzyskac surowe wartosci
JA3/JA4/Akamai Firefoksa 152, zeby skonfigurowac curl_cffi z wlasnym fingerprintem.
"""
import json
import time
from pathlib import Path

from camoufox import Camoufox

BASE_DIR = Path(__file__).resolve().parent
OUTPUT = BASE_DIR / "wynik_ja3_firefox152.json"

# Pełny fingerprint: ja3, ja3_hash, ja4, ja4_r, akamai, akamai_hash, http2, peetprint.
PEET_URL = "https://tls.peet.ws/api/all"


def main() -> None:
    result = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S")}

    with Camoufox(
        headless=True,
        os="windows",
        fingerprint_preset=True,
        humanize=True,
        # block_webgl celowo NIE ustawiamy — TLS fingerprint (JA3/JA4) jest
        # niezależny od WebGL, a chcemy zmierzyć czysty transport Firefoksa 152.
    ) as browser:
        page = browser.new_page()

        # Bezpośrednie goto na endpoint — TLS handshake wykonuje realny Firefox
        # (Camoufox). Odpowiedź to czysty JSON, sczytujemy ją z treści strony.
        resp = page.goto(PEET_URL, wait_until="domcontentloaded", timeout=60000)
        result["status"] = resp.status if resp else None
        try:
            body = (resp.body() if resp else b"").decode("utf-8", errors="replace")
        except Exception:
            body = page.content() if page else ""

        try:
            data = json.loads(body)
        except Exception:
            data = {"raw": body[:2000]}

        result["data"] = data

        # Wyciągnij najważniejsze pola osobno, żeby latwiej je potem odczytac.
        result["user_agent"] = page.evaluate("navigator.userAgent")
        result["ja3"] = data.get("ja3")
        result["ja3_hash"] = data.get("ja3_hash")
        result["ja4"] = data.get("ja4")
        result["akamai"] = data.get("akamai")
        result["akamai_hash"] = data.get("akamai_hash")

        print(json.dumps(
            {k: result.get(k) for k in (
                "status", "user_agent", "ja3", "ja3_hash", "ja4", "akamai", "akamai_hash"
            )},
            ensure_ascii=False,
            indent=2,
        ))

    result["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nZapisano wynik do: {OUTPUT}")


if __name__ == "__main__":
    main()