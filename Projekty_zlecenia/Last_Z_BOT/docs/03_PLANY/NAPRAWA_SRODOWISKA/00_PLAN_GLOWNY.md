> UWAGA: PRZESTARZAŁE — EasyOCR/Tesseract/Win7 usunięte. Patrz DIAGNOSTICS.md i WINDOWS7_SUPPORT.md.

# Plan naprawy: bot odporny na środowisko + gotowy do dystrybucji SaaS

Cel: bot ma działać u KAŻDEGO klienta końcowego, niezależnie od skali DPI, monitorów, uprawnień, rozdzielczości, sprzętu i wersji Windowsa. A także: dać się sprzedać wielu osobom (podpis, instalator, aktualizacje, licencje).

## PRIORYTET 1 — Środowisko (żeby w ogóle działało u klienta)

| # | Fix | Plik | Status |
|---|---|---|---|
| 1 | DPI / skalowanie Windows (Per-Monitor v2) | `01_DPI_SKALOWANIE.md` | DO ZROBIENIA |
| 2 | Multi-monitor / ujemne współrzędne + VIRTUALDESK | `02_MULTI_MONITOR.md` | DO ZROBIENIA |
| 3 | Administrator / UIPI (manifest requireAdministrator) | `03_ADMIN_UIPI.md` | DO ZROBIENIA |
| 4 | Rozdzielczość ≠ 1920x1080 (hardcoded) | `04_ROZDZIELCZOSC.md` | DO ZROBIENIA |
| 5 | Szum kliknięcia > próg kamery | `05_SZUM_KLIKNIECIA.md` | DO ZROBIENIA |
| 6 | Zbędny MOUSEEVENTF_MOVE w spamie | `06_MOUSEEVENTF_MOVE.md` | DO ZROBIENIA |

## PRIORYTET 2 — Dystrybucja (żeby bot dotarł i ruszył u klienta)

| # | Fix | Plik | Status |
|---|---|---|---|
| 7 | Przejście z onefile na standalone + Inno Setup | `07_BUILD_STANDALONE.md` | DO ZROBIENIA |
| 8 | Podpis cyfrowy (Azure Artifact Signing) + SmartScreen | `08_PODPIS_SMARTSCREEN.md` | DO ZROBIENIA |
| 9 | VC++ Redistributable w instalatorze | `09_VC_REDIST.md` | DO ZROBIENIA |
| 10 | EasyOCR → PaddleOCR ONNX + DirectML (CPU 100% → <5%, 270MB → 35MB) | `10_OCR_ONNX_DIRECTML.md` | DO ZROBIENIA |
| 11 | Format kolorów BGR/RGB + HDR fallback | `11_FORMAT_KOLOROW_HDR.md` | DO ZROBIENIA |
| 12 | Kaskada GPU (DXGI → WGC → GDI) | `12_KASKADA_GPU.md` | DO ZROBIENIA |
| 13 | FPS mode 30/60/120/144 Hz | `13_FPS_MODES.md` | DO ZROBIENIA |

## PRIORYTET 3 — Backend licencyjny / SaaS (żeby biznes działał)

| # | Fix | Plik | Status |
|---|---|---|---|
| 14 | Backend: brak klucza prywatnego → 503, crypto, klucz publiczny | `14_BACKEND_LICENCJA.md` | DO ZROBIENIA |
| 15 | Stripe: client_reference_id zamiast email + webhook subskrypcji | `15_STRIPE_WEBHOOK.md` | DO ZROBIENIA |
| 16 | Trwały HWID (CPU+board+BIOS UUID) | `16_HWID_TRWALY.md` | DO ZROBIENIA |
| 17 | NetworkTimeProvider (JWT trusted time) | `17_NTP_TIME.md` | DO ZROBIENIA |
| 18 | Frontend zakupowy (strona kupna licencji) | `18_FRONTEND_ZAKUP.md` | DO ZROBIENIA |
| 19 | Bootstrap admina | `19_BOOTSTRAP_ADMIN.md` | DO ZROBIENIA |

## PRIORYTET 4 — Ciche awarie i stabilność

| # | Fix | Plik | Status |
|---|---|---|---|
| 20 | Brak kroku odbioru nagrody po WATCH_TIMER | `20_ODBIOR_NAGRODY.md` | DO ZROBIENIA |
| 21 | DXCam cache 5s serwuje zamrożony timer | `21_DXCAM_CACHE.md` | DO ZROBIENIA |
| 22 | dpg.set_value z wątku tła → zawieszenia | `22_GUI_WATEK.md` | DO ZROBIENIA |
| 23 | Wyścig wątków hotkeyi | `23_HOTKEY_WYSCIG.md` | DO ZROBIENIA |
| 24 | Locale / separator dziesiętny / ścieżki (kodowanie logów już UTF-8) | `24_LOCALE_ENCODING.md` | DO ZROBIENIA |
| 25 | Pre-flight Diagnostic Wizard + Sentry | `25_DIAGNOSTYKA.md` | DO ZROBIENIA |

## Kolejność realizacji (rekomendowana)
1. **P1** (1-6) — bot działa u klienta, którego już mamy (spór Useme)
2. **P2** (7-13) — bot działa u KAŻDEGO klienta i dociera bez blokad AV/SmartScreen
3. **P3** (14-19) — biznes licencyjny działa (klient sprzedaje subskrypcje)
4. **P4** (20-25) — stabilność i wsparcie

## Źródła
- Deep audit kod (08_DEEP_AUDIT_UKRYTE_BLEDY.md)
- Audyt dystrybucji Windows SaaS (zarchiwizowany w 07_ARCHIWUM)
- Audyt Gemini (06_GEMINI_AUDYT_BLEDOW)