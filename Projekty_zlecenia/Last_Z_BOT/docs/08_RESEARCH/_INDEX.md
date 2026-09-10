# Indeks tematów researchu

Każdy temat = plik z otwartym pytaniem badawczym, neutralnym wobec rozwiązania. Wynikają z bugów znalezionych w kodzie (patrz `05_BUGI_KLIENTA` i `03_PLANY/NAPRAWA_SRODOWISKA`).

| # | Temat | Rozwiązuje problem |
|---|---|---|
| 01 | Latencja OCR i silniki ONNX | CPU 100%, lag 1.5-3.4s, build 270MB |
| 02 | Input injection: UIPI i integralność | bot nie klika gdy gra jest jako admin |
| 03 | DXGI capture: HAGS, multi-GPU, HDR | czarny ekran / zła detekcja na różnym sprzęcie |
| 04 | Stripe webhook i aktywacja licencji | licencja nie aktywuje się po płatności |
| 05 | DearPyGui: thread safety | zawieszanie GUI (crash) |
| 06 | Windows locale i kodowanie | crash na polskim/niemieckim Windowsie |

## Dlaczego te, a nie inne
- Każdy ma dowód w kodzie (plik + linia) — research da konkretną receptę
- Nie dublują się nawzajem
- Dystrybucja (podpis, standalone) i trwały HWID → odłożone do `09_POZNIEJ` (wymagają decyzji biznesowej albo nie blokują teraz)

## Jak używać
Każdy plik to gotowy prompt do WebSearch. Odpalaj po jednym, a wynik zapisuj z powrotem do planu naprawy.