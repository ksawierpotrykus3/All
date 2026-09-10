"""
Cortex Agent — minimalny szkielet wykonawczy.

Dostaje cel (zwykły tekst) i wykonuje prostą automatyzację przeglądarkową
przy pomocy Playwright. Na bieżąco zapisuje stan do miejsca, które czyta
moduł Supervisor w Cortexie: data/pipelines/<id>/stan.json.

Kontrakt stan.json jest zgodny z src/supervisor/schema.json oraz
src/main/storage/StorageEngine.ts.

Użycie:
    python agent.py "pobierz treść strony https://example.com"
    python agent.py --auto-approve   # test end-to-end bez czekania na bramkę
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Brak Playwright. Zainstaluj: pip install playwright && playwright install chromium")
    sys.exit(1)


# Ścieżki
CORTEX_ROOT = Path(__file__).resolve().parent.parent
PIPELINES_DIR = CORTEX_ROOT / "data" / "pipelines"

# Ustawienia
PIPELINE_ID = "agent_przyklad"
DOMYSLNY_CEL = "pobierz treść strony https://example.com"
DOCELOWY_URL = "https://example.com"
MAX_DLUGOSC_TRESCI = 500
INTERWAL_POLLINGU_S = 1.0
MAKS_CZAS_CZEKANIA_S = 120

STATUS_W_TOKU = "w_toku"
STATUS_ZROBIONE = "zrobione"
STATUS_CZEKA = "czeka_na_ciebie"
STATUS_BLAD = "blad"
STATUS_ZAKONCZONO = "zakonczono"


def teraz() -> str:
    """Znacznik czasu UTC w formacie ISO 8601."""
    return datetime.now(timezone.utc).isoformat()


def zapisz_stan(pipeline_id: str, stan: dict) -> Path:
    """Zapisuje stan.json atomowo (tmp -> rename)."""
    katalog = PIPELINES_DIR / pipeline_id
    katalog.mkdir(parents=True, exist_ok=True)
    sciezka = katalog / "stan.json"
    tmp = katalog / "stan.json.tmp"
    tmp.write_text(json.dumps(stan, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, sciezka)
    return sciezka


def sciezka_decyzji(pipeline_id: str) -> Path:
    return PIPELINES_DIR / pipeline_id / "decyzja.json"


def wyczysc_decyzje(pipeline_id: str) -> None:
    """Usuwa stary plik decyzji, żeby agent nie przeczytał nieświeżej odpowiedzi."""
    sciezka = sciezka_decyzji(pipeline_id)
    if sciezka.exists():
        sciezka.unlink()


def nowy_krok(krok_id, nazwa: str, typ: str, status: str, **extra) -> dict:
    """Buduje pojedynczy krok zgodnie z kontraktem Supervisor."""
    krok = {
        "id": krok_id,
        "nazwa": nazwa,
        "typ": typ,
        "status": status,
    }
    krok.update(extra)
    return krok


def nowy_stan(cel: str) -> dict:
    return {
        "id": PIPELINE_ID,
        "nazwa": "Agent przeglądarkowy",
        "opis": cel,
        "silnik": "Python + Playwright",
        "wyzwalacz": "manual",
        "wyzwalacz_typ": "manual",
        "status_ogolny": STATUS_W_TOKU,
        "created_at": teraz(),
        "kroki": [],
    }


def czekaj_na_decyzje(pipeline_id: str, krok_id) -> str | None:
    """Czeka na plik decyzja.json dla danego kroku. Zwraca decision lub None."""
    sciezka = sciezka_decyzji(pipeline_id)
    limit_iteracji = int(MAKS_CZAS_CZEKANIA_S / INTERWAL_POLLINGU_S)
    for _ in range(limit_iteracji):
        if sciezka.exists():
            try:
                dane = json.loads(sciezka.read_text(encoding="utf-8"))
                if str(dane.get("stepId")) == str(krok_id):
                    return dane.get("decision")
            except (json.JSONDecodeError, OSError):
                pass
        time.sleep(INTERWAL_POLLINGU_S)
    return None


def uruchom(cel: str, auto_approve: bool = False) -> None:
    wyczysc_decyzje(PIPELINE_ID)
    stan = nowy_stan(cel)

    def zapisz() -> None:
        stan["updated_at"] = teraz()
        zapisz_stan(PIPELINE_ID, stan)

    # Krok 1: przygotowanie przeglądarki
    stan["kroki"].append(
        nowy_krok(1, "Przygotowanie przeglądarki", "kod", STATUS_W_TOKU,
                  narzedzie="Playwright",
                  logi=["Uruchamiam przeglądarkę (headless)..."])
    )
    zapisz()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            stan["kroki"][0]["status"] = STATUS_ZROBIONE
            stan["kroki"][0]["logi"].append("Przeglądarka uruchomiona.")
            zapisz()

            # Krok 2: pobranie treści (z bramką decyzji)
            stan["kroki"].append(
                nowy_krok(2, "Pobierz treść strony", "kod", STATUS_W_TOKU,
                          narzedzie="Playwright",
                          logi=["Otwieram stronę..."])
            )
            zapisz()

            page = browser.new_page()
            page.goto(DOCELOWY_URL, wait_until="domcontentloaded")
            tytul = page.title()
            tresc = page.inner_text("body")[:MAX_DLUGOSC_TRESCI]

            stan["kroki"][1]["status"] = STATUS_CZEKA
            stan["kroki"][1]["wejscie"] = cel
            stan["kroki"][1]["wyjscie"] = f"Tytuł: {tytul}\n\n{tresc}"
            stan["kroki"][1]["logi"].append("Pobrano treść strony.")
            stan["kroki"][1]["wymaga_akceptacji"] = True
            stan["kroki"][1]["decyzja"] = {
                "pytanie": "Czy zapisać pobraną treść do pliku dokumentacji?",
                "wymaga_komentarza": False,
                "opcje": [
                    {"akcja": "approve", "etykieta": "Zatwierdź", "styl": "primary"},
                    {"akcja": "reject", "etykieta": "Odrzuć", "styl": "danger"},
                ],
            }
            zapisz()

            decyzja = "approve" if auto_approve else czekaj_na_decyzje(PIPELINE_ID, 2)

            if decyzja == "approve":
                # Krok 3: zapis dokumentacji
                stan["kroki"][1]["status"] = STATUS_ZROBIONE
                stan["kroki"].append(
                    nowy_krok(3, "Zapisz dokumentację", "kod", STATUS_W_TOKU,
                              narzedzie="Python",
                              logi=["Zapisuję do pliku..."])
                )
                zapisz()

                katalog = PIPELINES_DIR / PIPELINE_ID
                plik = katalog / "dokumentacja.txt"
                plik.write_text(
                    f"Cel: {cel}\n\nTytuł strony: {tytul}\n\nTreść:\n{tresc}",
                    encoding="utf-8",
                )

                stan["kroki"][2]["status"] = STATUS_ZROBIONE
                stan["kroki"][2]["wyjscie"] = str(plik)
                stan["kroki"][2]["logi"].append("Dokumentacja zapisana.")
                stan["kroki"][2]["pliki"] = [
                    {"nazwa": "dokumentacja.txt", "sciezka": str(plik)}
                ]
                stan["status_ogolny"] = STATUS_ZAKONCZONO
            else:
                stan["kroki"][1]["status"] = STATUS_BLAD
                stan["kroki"][1]["logi"].append("Odrzucono przez użytkownika.")
                stan["status_ogolny"] = STATUS_ZAKONCZONO

            zapisz()
            browser.close()
    except Exception as exc:
        # Zapisz błąd, żeby Supervisor pokazał problem zamiast wisieć w „w_toku".
        for krok in stan["kroki"]:
            if krok["status"] == STATUS_W_TOKU:
                krok["status"] = STATUS_BLAD
                krok.setdefault("logi", []).append(f"Błąd: {exc}")
        stan["status_ogolny"] = STATUS_BLAD
        zapisz()
        raise

    print(f"Zakończono. Stan zapisany w: {PIPELINES_DIR / PIPELINE_ID / 'stan.json'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cortex Agent — minimalny szkielet")
    parser.add_argument("cel", nargs="?", default=DOMYSLNY_CEL,
                        help="Cel automatyzacji (tekst)")
    parser.add_argument("--auto-approve", action="store_true",
                        help="Automatycznie zatwierdź bramkę decyzyjną (test end-to-end)")
    args = parser.parse_args()
    uruchom(args.cel, auto_approve=args.auto_approve)


if __name__ == "__main__":
    main()