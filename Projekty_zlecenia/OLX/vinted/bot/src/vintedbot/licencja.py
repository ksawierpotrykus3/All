"""Weryfikacja licencji offline (Ed25519).

Klient ma TYLKO klucz publiczny (wbudowany poniżej) — nie może podrobić
licencji. Developer trzyma klucz prywatny (poza folderem bota) i generuje
nowy plik `licencja.json` co miesiąc po zapłacie.

Format licencja.json:
    {
      "klient": "smartcare",
      "data_start": "2026-09-04",
      "data_koniec": "2026-10-04",
      "podpis": "base64(podpis Ed25519 nad kanonicznym stringiem)",
      "licencja_id": "dowolny_identyfikator"
    }

Kanoniczny string do podpisu (po jednym polu na linie, bez spacji):
    klient=<klient>
    start=<data_start>
    koniec=<data_koniec>
    id=<licencja_id>

Weryfikacja: podpis musi pasować do klucza publicznego ORAZ dzisiejsza data
musi być w przedziale [data_start, data_koniec]. Po terminie bot odmawia startu.
"""
import base64
import json
from datetime import date, datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

# Klucz PUBLICZNY developera (bezpieczny do osadzenia w kodzie klienta).
PUBLIC_KEY_B64 = "b5YFIKmMc/w6eRpL6oPYq+S1PGgUXvvetzqYv+WAj1c="

DEFAULT_LICENCJA_PATH = Path(__file__).resolve().parent.parent.parent / "licencja.json"


def _klucz_publiczny() -> Ed25519PublicKey:
    raw = base64.b64decode(PUBLIC_KEY_B64)
    return Ed25519PublicKey.from_public_bytes(raw)


def _kanoniczny_payload(data: dict) -> str:
    return (
        f"klient={data.get('klient', '')}\n"
        f"start={data.get('data_start', '')}\n"
        f"koniec={data.get('data_koniec', '')}\n"
        f"id={data.get('licencja_id', '')}"
    )


def wczytaj_licencje(path: Path | None = None) -> dict:
    """Wczytuje licencja.json. Rzuca wyjątek gdy brak/uszkodzony plik."""
    p = path or DEFAULT_LICENCJA_PATH
    return json.loads(Path(p).read_text(encoding="utf-8"))


def zweryfikuj_licencje(data: dict, dzis: date | None = None) -> tuple[bool, str]:
    """Zwraca (czy_ok, komunikat). Sprawdza podpis Ed25519 i datę ważności."""
    dzis = dzis or date.today()

    # 1. Podpis.
    podpis_b64 = data.get("podpis", "")
    if not podpis_b64:
        return (False, "brak podpisu w licencji")
    try:
        podpis = base64.b64decode(podpis_b64)
    except Exception:
        return (False, "podpis nieprawidłowy (nie base64)")

    klucz = _klucz_publiczny()
    payload = _kanoniczny_payload(data).encode("utf-8")
    try:
        klucz.verify(podpis, payload)
    except InvalidSignature:
        return (False, "podpis NIEZGODNY — licencja podrobiona albo uszkodzona")
    except Exception as exc:
        return (False, f"błąd weryfikacji podpisu: {exc!r}")

    # 2. Data ważności.
    try:
        start = datetime.strptime(data.get("data_start", ""), "%Y-%m-%d").date()
        koniec = datetime.strptime(data.get("data_koniec", ""), "%Y-%m-%d").date()
    except Exception:
        return (False, "brak poprawnej daty w licencji")

    if dzis < start:
        return (False, f"licencja ważna od {start}, dziś jest {dzis}")
    if dzis > koniec:
        return (False, f"licencja wygasła {koniec}. Odnów u dostawcy bota.")

    return (True, f"licencja ważna do {koniec}")


def sprawdz_licencje_na_starcie(path: Path | None = None) -> None:
    """Wczytuje i weryfikuje licencję. Rzuca SystemExit gdy nieważna.

    Wywoływane na początku runner.run(). Jeśli licencja zła — bot przestaje
    działać (to jest cel: klient nie może używać bota po terminie).
    """
    p = path or DEFAULT_LICENCJA_PATH
    try:
        data = wczytaj_licencje(p)
    except FileNotFoundError:
        print("BRAK PLIKU licencja.json — skontaktuj się z dostawcą bota.")
        raise SystemExit(1)
    except Exception as exc:
        print(f"Nie udało się wczytać licencji: {exc}")
        raise SystemExit(1)

    ok, komunikat = zweryfikuj_licencje(data)
    print(f"Licencja: {komunikat}")
    if not ok:
        print("Bot zatrzymany — licencja nieważna lub wygasła.")
        raise SystemExit(1)


__all__ = [
    "sprawdz_licencje_na_starcie",
    "zweryfikuj_licencje",
    "wczytaj_licencje",
]