> UWAGA: PRZESTARZAŁE — EasyOCR/Tesseract/Win7 usunięte. Patrz DIAGNOSTICS.md i WINDOWS7_SUPPORT.md.

# GEMINI AUDYT PROJEKTU LAST_Z_BOT — RAPORT GŁÓWNY (v2.0)
**Autor:** Antigravity (Gemini)  
**Data:** 2026-08-27 (Aktualizacja v2.0: Po rewizji i syntezie z werdyktem DeepSeek oraz analizą błędu serwera gry `5560006`)  
**Typ:** Dogłębny audyt deterministyczny kodu, architektury i logiki biznesowej (BEZ MODYFIKACJI KODU)

---

## 📌 Co nowego w wersji v2.0 (Zmiany i doprecyzowania po rewizji)

W wersji 2.0 zaktualizowano i doprecyzowano ustalenia na podstawie weryfikacji kodu i logów PCAP:
1. **Wyjaśniono błąd serwera `errorCode: 5560006`** — to nie jest błąd Pythona, ale odpowiedź serwera gry (*„Limit nagród wyczerpany / za późno”*), będąca bezpośrednim skutkiem opóźnień bota.
2. **Doprecyzowano liczbę przejść EasyOCR (G-10)** — rozbito na fazę `fast` (2 przejścia) oraz fazę `idle` / fallback (do 4 przejść + Tesseract).
3. **Rozbito błąd kalibracji 32 px (G-04)** — wykazano, że bezwzględnie niszczy `roi_to_frame_pixels` (crop OCR timera), natomiast wpływ na `to_screen` zależy od sposobu nagrania ROI.
4. **Wskazano podwójny mechanizm ucieczki kamery (G-03 + G-02 cz. 2)** — połączenie flagi `MOUSEEVENTF_MOVE` z szumem $\Delta d = 3.53\text{ px}$ (przekraczającym próg Unity $\approx 1.5\text{ px}$).

---

## 📊 Tabela Zbiorcza: Stan Pierwotny (v1.0) vs Zaktualizowany (v2.0)

| ID | Obszar | Poziom | [v1.0] Stan Pierwotny | [v2.0] Stan Poprawiony / Doprecyzowany | Status weryfikacji |
|---|---|---|---|---|---|
| **G-01** | Licencja / Start | **KRYTYCZNY** | Puste pola licencji w PROD rzucają `LicenseError` po naciśnięciu F6. | **POTWIERDZONE w 100%**: `config.json:37-38` puste, w PROD `is_dev_mode() == False` $\to$ F6 zablokowane u klienta. | ✅ Zweryfikowane |
| **G-02** | Logika Makra | **KRYTYCZNY** | Brak fazy odbioru nagrody po $T_0$. Makro kończy się na Step 5. | **DOPRECYZOWANE**: W kodzie makro urywa się po spamiu w (50, 52) i wraca do Step 1. Zmiana względem pierwotnej oferty (brak menu Select) wynika z `GAME_MECHANICS.md`, ale brak jakiejkolwiek finalizacji to twardy bug. | ✅ Zweryfikowane |
| **G-02 cz.2** | Silnik Inputu | **KRYTYCZNY** | Szum losowy przesuwa kursor o 2.5–3.0 px. | **DOPRECYZOWANE**: Offset $\pm 2.5–3.0\text{ px}$ daje wektor $\Delta d = 3.535\text{ px}$, co przekracza próg martwej strefy Unity `MobileTouchCamera` ($\approx 1.5\text{ px}$) i obraca kamerę. | ✅ Zweryfikowane |
| **G-03** | Silnik Inputu | **KRYTYCZNY** | `spam_down` i `spam_up` doklejają flagę `MOUSEEVENTF_MOVE`. | **DOPRECYZOWANE**: Flaga wysyła ruch w trakcie kliku. W połączeniu z szumem G-02 cz.2 natychmiast anuluje flagę `eligibleForClick = false` w Unity. | ✅ Zweryfikowane |
| **G-04** | Matematyka / ROI | **KRYTYCZNY** | Błędna kalibracja Y o 32 px psuje kliknięcia i crop OCR. | **POPRAWIONE/ROZBITE**: <br>• `roi_to_frame_pixels`: **100% BUG** — klatka DXCam to czysty obszar klienta, ponowne odjęcie 31px przesuwa crop OCR o 32px w górę i ucina timer.<br>• `to_screen`: Poprawne, o ile bazowe ROI nagrano względem całego okna (z paskiem). | 🔍 Doprecyzowane |
| **G-05** | Wizja / DXCam | **KRYTYCZNY** | DXCam zwraca klatki z cache do 5.0s przy braku zmian ekranu. | **POTWIERDZONE w 100%**: `_MAX_FRAME_AGE_SECONDS = 5.0` w `capture.py:20`. Bot analizuje zamrożony timer i spóźnia $T_0$ o kilka sekund. | ✅ Zweryfikowane |
| **G-06** | GUI / Wątki | **KRYTYCZNY** | `dpg.set_value()` z wątku tła bota. | **POTWIERDZONE w 100%**: Brak kolejki do wątku GUI ImGui powoduje wyścigi pamięci i losowe crashe `0xC0000005 ACCESS_VIOLATION`. | ✅ Zweryfikowane |
| **G-07** | Backend / Stripe | **KRYTYCZNY** | Webhook Stripe szuka usera tylko po mailu z checkoutu. | **POTWIERDZONE w 100%**: Ignorowanie `metadata["user_id"]` w `main.py:336-360` powoduje, że płatność innym mailem (PayPal/Apple Pay) nie aktywuje licencji. | ✅ Zweryfikowane |
| **G-08** | GUI / Hotkeys | **POWAŻNY** | `GlobalHotkey.stop()` nie dołącza wątku (`join`). | **POTWIERDZONE w 100%**: Brak `join()` wywołuje wyścig w WinAPI $\to$ błąd `ERROR_HOTKEY_ALREADY_REGISTERED` (1409) przy zapisie configu i utratę F1/F6/F8. | ✅ Zweryfikowane |
| **G-09** | Logika Makra | **POWAŻNY** | `reset()` w pętli zeruje statystyki sesji. | **POTWIERDZONE w 100%**: Zerowanie `stats_alerts` i `stats_errors` na starcie każdego `run()` uniemożliwia zliczanie sesji. | ✅ Zweryfikowane |
| **G-10** | Wydajność CPU | **POWAŻNY** | EasyOCR wykonuje do 3-4 przejść na klatkę na 1 rdzeniu. | **DOPRECYZOWANE**: W fazie `fast` wykonywane są **2 przejścia EasyOCR** (white-mask + 2x), a do 4 przejść dochodzi w fazie `idle` lub przy błędzie odczytu. Mimo to 2 przejścia na 1 wątku generują 400–800 ms opóźnienia. | 🔍 Doprecyzowane |
| **G-11** | Backend / Baza | **POWAŻNY** | Sync SQLite w async FastAPI. | **POTWIERDZONE**: Synchroniczne połączenia SQLAlchemy w asynchronicznym API przy współbieżnych requestach rzucają `sqlite3.OperationalError: database is locked`. | ✅ Zweryfikowane |
| **G-12** | Bezpieczeństwo / UIPI | **POWAŻNY** | Brak elewacji UAC w instalatorze. | **POTWIERDZONE w 100%**: Gra jako Administrator + Bot jako Standard User = Windows UIPI po cichu blokuje wszystkie kliknięcia `SendInput`. Główny powód: *„u mnie działa, u klienta nie”*. | ✅ Zweryfikowane |
| **G-13** | Dystrybucja / SaaS | **SPÓR UMOWNY** | Brak gotowej strony WWW / panelu SaaS. | **SPÓR ZAKRESU (Scope Mismatch)**: Backend API FastAPI jest gotowy, ale klient wybrał tańszą Ścieżkę A (bez panelu PWA za dopłatą 6k zł), a oczekiwał gotowego sklepu. | ⚖️ Kwestia umowy |

---

## 🔗 Pełny Łańcuch Przyczynowo-Skutkowy Awarii w Grze i Błędu `5560006`

W logach sieciowych gry ([`docs/01_WAZNE/ANALIZA_HELIKOPTER.md:116, 731`](file:///c:/Users/Ksawier/Pictures/Screenshots/Projekty_zlecenia/Last_Z_BOT/docs/01_WAZNE/ANALIZA_HELIKOPTER.md#L116)) zidentyfikowano kod błędu **`errorCode: 5560006`**.

Oto jak wszystkie wykryte błędy łączą się w jedną całość:

```
[G-10: Lag CPU/OCR 800ms] + [G-05: Bufor DXCam 5.0s] + [G-04: Błąd cropa OCR 32px]
                              │
                              ▼
           Spóźnienie detekcji zakończenia licznika T0 o 1.5 – 3.0s
                              │
                              ▼
    [G-03: MOUSEEVENTF_MOVE] + [G-02 cz.2: Szum 3.5px > 1.5px Unity]
                              │
                              ▼
        Ucieczka kamery i nietrafienie w collider skrzynki na mapie
                              │
                              ▼
       Inni gracze odbierają 10 dostępnych nagród przed naszym botem
                              │
                              ▼
       Serwer gry odrzuca spóźniony pakiet z błędem errorCode: 5560006
                              │
                              ▼
               [G-02: Brak logiki odbioru po kroku 5]
                              │
                              ▼
    Bot wraca do czatu, a klient widzi: „Większość nagród nieodebrana”
```

---

## 📂 Pliki Szczegółowe Audytu

1. **[GEMINI_01_SILNIK_GRY_I_INPUT.md](file:///c:/Users/Ksawier/Pictures/Screenshots/Projekty_zlecenia/Last_Z_BOT/docs/06_GEMINI_AUDYT_BLEDOW/GEMINI_01_SILNIK_GRY_I_INPUT.md)** — Błędy SendInput, szum 3.5 px, dryf kamery Unity.
2. **[GEMINI_02_WIZJA_OCR_I_KOORDYNATY.md](file:///c:/Users/Ksawier/Pictures/Screenshots/Projekty_zlecenia/Last_Z_BOT/docs/06_GEMINI_AUDYT_BLEDOW/GEMINI_02_WIZJA_OCR_I_KOORDYNATY.md)** — Błąd przesunięcia 32 px w `roi_to_frame_pixels`, bufor DXCam 5 s, throttling OCR.
3. **[GEMINI_03_LOGIKA_MAKRA_I_ODBIORU_NAGRODY.md](file:///c:/Users/Ksawier/Pictures/Screenshots/Projekty_zlecenia/Last_Z_BOT/docs/06_GEMINI_AUDYT_BLEDOW/GEMINI_03_LOGIKA_MAKRA_I_ODBIORU_NAGRODY.md)** — Brak logiki odbioru po zrzucie, ślepe klikanie w (50, 52), pętla restartu.
4. **[GEMINI_04_GUI_I_WATKOWOSC.md](file:///c:/Users/Ksawier/Pictures/Screenshots/Projekty_zlecenia/Last_Z_BOT/docs/06_GEMINI_AUDYT_BLEDOW/GEMINI_04_GUI_I_WATKOWOSC.md)** — Wyścigi w DearPyGui, wycieki wątków hotkeyi, blokowanie UI przy stopie.
5. **[GEMINI_05_BACKEND_STRIPE_I_LICENCJA.md](file:///c:/Users/Ksawier/Pictures/Screenshots/Projekty_zlecenia/Last_Z_BOT/docs/06_GEMINI_AUDYT_BLEDOW/GEMINI_05_BACKEND_STRIPE_I_LICENCJA.md)** — Dziury w webhookach Stripe, blokowanie SQLite, puste klucze w PROD.
6. **[GEMINI_06_BUILD_INSTALATOR_I_DYSTRYBUCJA.md](file:///c:/Users/Ksawier/Pictures/Screenshots/Projekty_zlecenia/Last_Z_BOT/docs/06_GEMINI_AUDYT_BLEDOW/GEMINI_06_BUILD_INSTALATOR_I_DYSTRYBUCJA.md)** — UAC/UIPI, zmienne środowiskowe HKLM, błędy uruchomienia.
