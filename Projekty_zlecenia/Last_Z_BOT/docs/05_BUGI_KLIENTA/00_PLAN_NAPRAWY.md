# Plan naprawy — problemy klienta

Zarzuty klienta rozbite na osobne problemy techniczne. Każdy ma osobny plik analizy.

| # | Problem | Plik analizy | Status |
|---|---|---|---|
| 1 | F6/START nie uruchamia bota (licencja) | `02_PROBLEM_F6_LICENCJA.md` | ZDIAGNOZOWANE |
| 2 | Bot nie odbiera nagrody po przylocie | `03_PROBLEM_ODBIOR_NAGRODY.md` | DO ANALIZY |
| 3 | Większość helikopterów niekliknięta | `03_PROBLEM_ODBIOR_NAGRODY.md` | DO ANALIZY |
| 4 | Wysokie zużycie CPU (OCR) | `04_PROBLEM_CPU_OCR.md` | DO ANALIZY |
| 5 | Zawieszanie się programu | `05_PROBLEM_ZAWIESZANIE.md` | DO ANALIZY |
| 6 | Nieprawidłowe czasy reakcji | `06_PROBLEM_CZASY_REAKCJI.md` | DO ANALIZY |

## Zależności
- Problem 1 (F6) jest warunkiem wstępnym — bez niego klient nic nie przetestuje. Już zdiagnozowany: PROD z pustym `backend_url`/`license_key` blokuje start. Rozwiązanie: wersja DEV (już wysłana klientowi).
- Problemy 2-6 to realne bugi bota, które trzeba naprawić zanim klient potwierdzi działanie DEV.

## Kolejność pracy
1. Najpierw analiza wszystkich bugów równolegle (subagenci).
2. Potem naprawa wg priorytetu: odbiór nagrody (2-3) > CPU (4) > czasy reakcji (6) > zawieszanie (5).