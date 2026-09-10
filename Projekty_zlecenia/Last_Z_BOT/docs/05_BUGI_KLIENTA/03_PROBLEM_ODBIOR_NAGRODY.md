> UWAGA: PRZESTARZAŁE — EasyOCR/Tesseract/Win7 usunięte. Patrz DIAGNOSTICS.md i WINDOWS7_SUPPORT.md.

# Problem 2+3: Bot nie odbiera nagrody / helikoptery niekliknięte

## Status: ZDIAGNOZOWANE POPRAWNIE (po weryfikacji z dokumentami gry)

## Objawy klienta
- "bot przechodzi do helikoptera, ale następnie nie odbiera nagrody"
- "większość helikopterów pozostaje niekliknięta"

## KLUCZOWE USTALENIE (korekta wcześniejszej błędnej tezy)

**Klikanie w środek ekranu (50%, 52%) NIE jest bugiem — jest POPRAWNE.**

Dowód z dokumentów:
- GAME_MECHANICS.md linia 61: "Bot musi po prostu bardzo szybko klikać dokładnie w to samo miejsce (środek ekranu, gdzie stał helikopter - FULL SPEED SPAM)"
- ANALIZA_HELIKOPTER.md linia 14: "Helikopter jest na środku ekranu, klikanie trafia w środek."

Mechanika: bot klika koordynaty z czatu → kamera centruje się na helikopterze → helikopter = środek ekranu → skrzynka = miejsce helikoptera = środek ekranu. Więc cel (50%,52%) jest właściwy.

## PRAWDZIWY ŁAŃCUCH PRZYCZYNOWY

Nie chodzi o to GDZIE bot klika, tylko KIEDY. Łańcuch:

1. OCR (EasyOCR na 1 rdzeniu) ma lag **1.5–3.4 s** — dowód: ANALIZA_HELIKOPTER.md:398
2. → bot spóźnia się na T0 (nieprawidłowe czasy reakcji)
3. → dig (kliknięcie otwierające skrzynkę) dociera na serwer za późno, po innych graczach
4. → serwer zwraca **error 5560006 = limit nagród wyczerpany** — dowód: ANALIZA_HELIKOPTER.md:116
5. → klient widzi "bot nie odbiera nagrody" / "większość helikopterów niekliknięta"

## Dodatkowy fakt z dokumentów
- ANALIZA_HELIKOPTER.md:278: "Klik/mysz w grze NIE sterują digiem — diga wysyła klient gry na timerze"
- Ale bez klikania nie ma nagrody (potwierdzone przez usera) — więc kliknięcie jest warunkiem koniecznym, ale nie wystarczającym; liczy się też moment.

## Prawdziwe przyczyny problemu (w kolejności ważności)

### 1. Lag OCR 1.5–3.4s → spóźnienie na T0 (NAJWAŻNIEJSZE)
To jest korzeń. Patrz plik `04_PROBLEM_CPU_OCR.md`. CPU 100% przez EasyOCR powoduje, że timer jest odczytywany z opóźnieniem 1.5–3.4s, więc bot nie może trafić w moment pojawienia się skrzynki.

### 2. Fałszywe wyzwalanie spamu przy value is None
Plik: `mvp/macro_engine.py:1072-1084`
Gdy OCR nie odczyta timera (rozmyta klatka), bot błędnie zakłada "timer zniknął = skrzynka się pojawiła" i spamuje za wcześnie.

### 3. Brak weryfikacji sukcesu po spamie
Plik: `mvp/macro_engine.py:1136-1170`
Po spamie bot nie sprawdza czy nagroda odebrana, nie retry'uje przy error 5560006.

### 4. Spóźnienie na T0 (szczegóły w 05_PROBLEM_ZAWIESZANIE_I_CZASY.md)
- grab_mono przed grab() → T0 przesunięte w przeszłość
- sleep Event.wait ~15.6ms + Bezier 15-75ms

## Następny krok
Priorytet: naprawić lag OCR (CPU), bo on powoduje spóźnienie na T0, a to powoduje error 5560006 i "nie odbiera nagrody".