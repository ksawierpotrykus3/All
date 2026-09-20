# DOKUMENTACJA EKSPANSJI: System Automatyzacji i Skalowania Useme Bot

Dokument stanowi inżynierski plan rozwoju, skalowania i komercjalizacji ekosystemu useme_core. Określa, jak przejść od obecnego stabilnego generatora ofert do w pełni zautomatyzowanej maszyny pozyskującej zlecenia z rynku freelancerskiego w oparciu o twarde dane.

---

## 1. Architektura Wyjściowa (Stan Obecny - Baseline)

Aktualny silnik opiera się na architekturze hybrydowej (Neuro-Symbolic):
1. Slot 01 (Research): DeepSeek zbiera wiedzę techniczną i ograniczenia API z blokadą OSINT klienta.
2. Slot 02b (Klasyfikator): Model nie liczy kwoty, lecz zwraca znormalizowany JSON (moduły z dozwolonej taksonomii, godziny, flagi ryzyka).
3. Kalkulator Python (wycena_kalkulator.py): Deterministyczny silnik matematyczny egzekwujący bufor, testy, cap godzinowy (np. 25h dla One-Page) i stawkę bazową (90 zł/h).
4. Slot 02a (Generator Treści): Model pisze perswazyjną ofertę techniczną w oparciu o wyliczoną kwotę i fakty z researchu.
5. Slot 08 (Walidator): Automatyczny audytor sprawdzający zgodność z regułami biznesowymi.

---

## 2. Faza 1: Wywiad Rynkowy i Kalibracja Stawek (Market Reconnaissance)

Aby wyjść z próżni teoretycznej (mechanika_wyceniania.md), system musi oprzeć się na empirycznych danych o polskiej konkurencji.

### A. Operacja Honeypot (Profil Zleceniodawcy na Useme)
* Cel: Zgromadzenie 40–60 realnych ofert na zlecenie wzorcowe (np. Landing Page meblowy / Perca).
* BHP i Bezpieczeństwo Operacyjne:
  - Bezwzględna separacja środowisk: konto zleceniodawcy zakładane z poziomu innej sieci (IP komórkowe) i czystego profilu przeglądarki, aby wykluczyć powiązanie odcisków (fingerprinting) z kontem wykonawcy.
  - Zlecenie zamykane po 4 dniach ze statusem: Wybrany wykonawca z polecenia / projekt wstrzymany.
* Ekstrakcja Danych:
  - Zapis ofert do pliku JSON z polami: wykonawca, liczba umów, kwota, czas realizacji, treść oferty, wskaźniki AI.

### B. Analiza Statystyczna i Kalibracja Cennika
* Wyliczenie Mediany Peletonu: Odrzucenie skrajności (desperaci 300 zł vs drogie agencje 12 000 zł). Mediana doświadczonych wykonawców (>10 umów) staje się złotym punktem kalibracji w wycena_kalkulator.py.
* Baza Argumentów Sprzedażowych: Wyciągnięcie z najlepszych ofert realnych argumentów, które przekonują klientów, i zasilenie nimi pliku jak_pisac_oferty.md.

---

## 3. Faza 2: Pętla Sprzężenia Zwrotnego i Śledzenie Konwersji (Feedback Loop)

System produkcyjny musi wiedzieć, które oferty przynoszą realne odpowiedzi klientów.

1. Rejestr Wysłanych Ofert (magazyn/wyslane/):
   Każde zgłoszenie zapisuje pełny zrzut: job_id, kwota, dni, wybrane moduły, treść oferty, hash ogłoszenia.
2. Skrypt Monitorujący (tracker_statusu.py):
   Cykliczne sprawdzanie panelu Useme: czy klient odczytał ofertę, czy odpisał na czacie, kto wygrał zlecenie.
3. Wskaźnik Response-Rate:
   Obliczanie skuteczności per kategoria: (Odpowiedzi na czacie / Wysłane oferty) * 100%.

---

## 4. Faza 3: Dynamiczne Testy A/B i Samouczący się Cennik

1. Wariantowanie Treści Ofert (A/B Testing):
   Naprzemienne generowanie ofert w stylu techniczno-audytowym (skupionym na ryzykach i CWV) vs partnersko-biznesowym (korzyści i spokój klienta).
2. Dynamiczna Kalibracja Marży (Price Optimization):
   Podnoszenie stawki efektywnej w kategoriach o wysokiej konwersji (np. 90 -> 110 zł/h) i optymalizacja marży.

---

## 5. Faza 4: Skalowanie Horyzontalne i Tryb 24/7

1. Demon Czasu Rzeczywistego (First-Mover Advantage):
   Monitorowanie listy zleceń co 120s i automatyczne generowanie ofert w pierwszych minutach od publikacji.
2. Wielokanałowość:
   Wykorzystanie silnika wyceny na innych polskich tablicach zleceń B2B.

---

## 6. Inżynierska Macierz Ryzyka

1. Pętla błędów / Timeout Proxy -> Twardy timeout 120s na krok + limit 3 ponowień.
2. Dryf wyceny na nietypowym zleceniu -> Sztywne ograniczenia (Caps) w Pythonie per kategoria.
3. Wykrycie automatyzacji przez portal -> Losowe opóźnienia, symulacja ruchów myszy, brak stałych interwałów.
