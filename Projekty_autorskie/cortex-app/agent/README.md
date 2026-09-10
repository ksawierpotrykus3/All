# Cortex Agent — minimalny szkielet

Agent w Pythonie, który wykonuje prostą automatyzację przeglądarkową (Playwright)
i zapisuje jej stan do `data/pipelines/agent_przyklad/stan.json` — tam, skąd czyta
go moduł **Supervisor** w Cortexie.

## Wymagania

- Python 3.13+ (zainstalowany)
- Playwright: `pip install playwright`
- Przeglądarka Chromium: `playwright install chromium`

## Uruchomienie

```powershell
cd agent
python agent.py
```

Lub z własnym celem:

```powershell
python agent.py "pobierz treść strony https://example.com"
```

Test end-to-end bez czekania na bramkę:

```powershell
python agent.py --auto-approve
```

## Jak to działa

1. Agent uruchamia przeglądarkę w tle (niewidoczna).
2. Wchodzi na stronę i pobiera tytuł + treść.
3. Zapisuje stan do `data/pipelines/agent_przyklad/stan.json` w formacie czytelnym dla Supervisora.
4. Przy kroku "Pobierz treść strony" ustawia bramkę decyzji — czeka, aż w Cortexie klikniesz
   "Zatwierdź" lub "Odrzuć" (zapis do `decyzja.json`).
5. Po zatwierdzeniu zapisuje dokumentację do `dokumentacja.txt`.

## Zobacz w Cortexie

1. Uruchom Cortex (`npm run dev`).
2. Otwórz widok **Supervisor** (przycisk w prawym górnym rogu).
3. Powinna pojawić się karta "Agent przeglądarkowy" ze statusem i krokami.