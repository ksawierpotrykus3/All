# Fix 2: Multi-monitor / ujemne współrzędne

## Problem
Dwa osobne bugi:
1. `GetMonitorInfoW` bez `argtypes`/`restype` — na 64-bit obcina HMONITOR do 32 bitów → zwraca pustą listę monitorów → fallback do monitora 0
2. Monitor wtórny po lewej (ujemne współrzędne): `left = max(window_left - ml, 0)` daje ogromną wartość zamiast 0 → region poza ekranem

## Miejsce w kodzie
- `mvp/bot/monitor_mapper.py:41-60` — `GetMonitorInfoW` bez typów
- `mvp/bot/monitor_mapper.py:100-104` — obliczanie regionu

## Rozwiązanie
1. Dodać `argtypes`/`restype` do `GetMonitorInfoW` (i innych wywołań ctypes)
2. Poprawić wzór na region — używać poprawnych współrzędnych względem origin monitora

## Kroki
- [ ] Zadeklarować typy ctypes dla GetMonitorInfoW
- [ ] Przetestować na monitorze wtórnym po lewej od primary