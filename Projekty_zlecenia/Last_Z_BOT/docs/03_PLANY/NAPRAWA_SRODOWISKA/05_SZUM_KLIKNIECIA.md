# Fix 5: Szum kliknięcia — dwa osobne progi (kamera vs double-click)

## Problem (zaktualizowany 2026-09-03)

Silnik Unity ma **dwa niezależne filtry** z różnymi progami, które łatwo pomylić:

| Filtr | Próg | Co mierzy | Skutek przekroczenia |
|---|---|---|---|
| `BitBenderGames.MobileTouchCamera` | ~1.5 px | ruch **w trakcie** kliknięcia (DOWN→UP) | `eligibleForClick=false`, ucieczka kamery |
| `ClickDetector` | ~5.0 px + 300 ms | dystans **między** kolejnymi kliknięciami | sklejenie spamu w jeden gest |

Wcześniejsza wersja tego planu błędnie kazała zmniejszyć szum poniżej 1.5 px. To rozwiązywało ucieczkę kamery, ale **powodowało**, że cały spam (38 CPS → odstęp ~26 ms < 300 ms) był przez `ClickDetector` sklejany w jeden gest — gra rejestrowała tylko pierwszy klik.

## Poprawna zasada

1. **DOWN i UP na tych samych współrzędnych (Δr = 0)** — żaden `MOVE` w trakcie trzymania.
2. **Ruch ≥5 px wyłącznie w przerwie UP (state=0)** — rozdziela kliknięcia w `ClickDetector`.

## Miejsce w kodzie

- `mvp/bot/input/sendinput_backend.py` — `spam_down`/`spam_up` (usunięto `MOUSEEVENTF_MOVE`).
- `mvp/bot/clicker.py` — `_noise_offset()` (amplituda 2.5–3.0 px).

## Rozwiązanie (wdrożone)

1. `spam_down`/`spam_up` wysyłają tylko `ABSOLUTE | VIRTUALDESK | LEFTDOWN/UP` (bez `MOUSEEVENTF_MOVE`).
2. `_noise_offset()` generuje amplitudę `random.uniform(2.5, 3.0)` na osi, co daje dystans euklidesowy ~3.5–4.2 px, a ruch realizuje `spam_move` wyłącznie przy zwolnionym przycisku.

## Pozostałe kroki

- [x] Usunąć `MOUSEEVENTF_MOVE` z `spam_down`/`spam_up`
- [x] Przywrócić amplitudę szumu (separacja między kliknięciami)
- [x] Zaktualizować testy (`test_input_backend.py`) — 31/31 przechodzi
- [x] **Walidacja w grze/symulatorze (Wdrożono wrzesień 2026 - Podejście B):** Naprzemienne znaki na obu osiach dają dystans euklidesowy $D = 2\sqrt{2} \times \text{amp} \approx 5.6–8.5\text{ px} \ge 5.0\text{ px}$. Skutecznie omija filtr `ClickDetector` 300 ms, pozostając bezpiecznie wewnątrz collidera skrzynki (30x30 px). Ruch `spam_move` wyłącznie w stanie `UP` (split 40/60).