# Fix 6: Zbędny MOUSEEVENTF_MOVE w spamie

## Problem
`sendinput_backend.py:187-199` — DOWN/UP mają doklejone `MOUSEEVENTF_MOVE`. Unity może interpretować to jako `TouchPhase.Moved` i anulować kliknięcie (próg 1.5 px).

## Miejsce w kodzie
- `mvp/bot/input/sendinput_backend.py:187-199`

## Rozwiązanie
Usunąć `MOUSEEVENTF_MOVE` z `spam_down`/`spam_up` — kliknięcie bez ruchu.

## Kroki
- [ ] Usunąć flagę MOVE z DOWN/UP
- [ ] Test klikania — gra ma rejestrować czyste kliknięcia