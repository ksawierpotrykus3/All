# Plan — Bot OLX (od zera)

## 1. Cel

Zbudować od zera bota OLX, który:

1. **Wyprzedza wyszukiwarkę** — wykrywa nowe ogłoszenia szybciej, niż pojawią się one w normalnych wynikach wyszukiwania / na stronie OLX (metoda przewidywania ID).
2. **Sam siebie weryfikuje** — ma wbudowany komparator, który porównuje „kiedy my wykryliśmy ogłoszenie (przewidywanie ID)" z „kiedy to samo ogłoszenie pojawiło się w przeglądarce / wyszukiwarce" i **od razu wylicza przewagę w minutach**.
3. **Zero powiadomień** — brak Telegrama, brak webhooków, brak Discord. Wszystko idzie do **logów i do konsoli (cmd)**.

Priorytet: **tylko OLX**. Vinted zostaje na później.

---

## 2. Zakres

### W zakresie
- Monitoring kategorii/filtrów:
  - **iPhone'y** — cała Polska
  - **MacBooki** — cała Polska
  - **Auta do 12 000 zł** — Mazowsze
- Przewidywanie ID ogłoszeń (metoda z poprzedniej wersji bota).
- Moduł komparatora: nasza detekcja vs przeglądarka/wyszukiwarka, z liczeniem minut przewagi.
- Logowanie: konsola (cmd) + pliki logów, rotacja.

### Poza zakresem (na start)
- Vinted.
- Automatyczny zakup / checkout (OLX — na start tylko monitoring i detekcja; moduł Autobuy/Rezerwacja Przesyłki OLX rozpisany jako opcjonalne rozszerzenie w recon/08_autobuy_analiza_techniczna.md).
- Panel webowy / Web UI (na start CLI + logi).

---

## 3. Założenia (do potwierdzenia w fazie 0)

| # | Założenie | Jak zweryfikujemy |
|---|-----------|-------------------|
| Z1 | Klucz deweloperski OLX (Client ID `202745`) nadal działa i pozwala wysyłać **dużą liczbę requestów bez banów / rate-limitu** | Faza 0 — test połączenia + test obciążenia (wiele zapytań pod rząd) |
| Z2 | Metoda przewidywania ID nadal działa — ogłoszenia są najpierw dostępne w **głównej bazie OLX**, a ID są rosnące/sekwencyjne; na podstawie istniejących ogłoszeń da się wyliczyć ID tych, które dopiero wypłyną do wyszukiwarki | Faza 0 — próbka ID z głównej bazy, sprawdzenie ciągłości i przewidywalności |
| Z3 | Istnieje sposób odczytu ogłoszenia bezpośrednio z **głównej bazy OLX po ID** — szybciej, niż trafi ono do wyszukiwarki | Faza 0 — test odczytu po ID z głównej bazy |
| Z4 | Wyszukiwarka OLX (to, co widzi człowiek w przeglądarce) indeksuje nowe ogłoszenia z opóźnieniem względem bezpośredniego odczytu po ID | Faza 1 — pierwsze porównanie czasów |

> UWAGA — jak to naprawdę działa (potwierdzone przez klienta): Klucz deweloperski (Client ID `202745`) służy do wysyłania **dużej liczby requestów bez banów** (ochrona przed rate-limitem / blokadą). Sama przewaga (~10 min) wynika stąd, że ogłoszenia **już istnieją w głównej bazie OLX**, zanim pojawią się w wyszukiwarce. ID ogłoszeń są sekwencyjne, więc na podstawie ogłoszeń z głównej bazy da się **wyliczyć ID ogłoszeń, które dopiero wypłyną**. Bot czytał je po ID z głównej bazy i dzięki temu klient mógł dzwonić do ludzi, zanim oferta weszła do przeglądarki. Faza 0 potwierdza: (1) klucz pozwala robić dużo zapytań bez banów i (2) ID są przewidywalne na podstawie głównej bazy.

---

## 4. Architektura modułów

Bot będzie CLI w Pythonie (lub Node — decyzja przy starcie), podzielony na 4 moduły:

### M1 — Weryfikator API / endpointów (faza rozruchowa)
- Testuje klucz deweloperski (czy żyje, czy nie wygasł, czy API się nie zmieniło) **oraz czy pozwala na dużą liczbę requestów bez banów** (test obciążenia).
- Sprawdza dostęp do **głównej bazy OLX** i szybkość odczytu ogłoszeń po ID.
- Wynik: raport `PASS/FAIL` dla każdego źródła, zapisany w logach.

### M2 — Detektor (przewidywanie ID, „przed wyszukiwarką")
1. Dla każdej kategorii pobiera aktualne maksymalne ID ogłoszenia (baseline).
2. Buduje okno „przyszłych ID": `max_id + 1 … max_id + K` (K = margines, np. 50–200).
3. Odpytywał te ID bezpośrednio (odczyt ogłoszenia po ID) z wysoką częstotliwością (np. co 1–2 s, z jitterem).
4. Gdy przewidziane ID zacznie zwracać **realne ogłoszenie** pasujące do filtrów → zdarzenie detekcji z czasem `T_detect`.
5. Loguje: `ID`, tytuł, kategoria, link, `T_detect`.

### M3 — Komparator (przeglądarka vs my) + licznik minut
- Równolegle, z **wolniejszym** interwałem (np. co 15–30 s), odpytuje **wyszukiwarkę OLX** dla tych samych filtrów (tak, jak widzi to przeglądarka).
- Gdy ogłoszenie pojawi się w wynikach wyszukiwania → zapis `T_browser`.
- Dopasowuje to samo ogłoszenie po `ID` między M2 a M3.
- **Liczy natychmiast:** `przewaga[min] = (T_browser − T_detect)`.
- Obsługuje przypadki:
  - `przewaga > 0` → my szybciej (cel bota).
  - `przewaga = 0 / ujemna` → wyszukiwarka była równo lub szybciej → logowany „miss".
- Prowadzi statystyki bieżące: trafienia, chybienia, średnia / mediana / maksimum przewagi.

### M4 — Logger (zero powiadomień)
- Wszystko do:
  - **stdout (cmd/konsola)** — czytelne linie z timestampem i poziomem (INFO/WARN/ERROR), plus okresowa tabela wyników.
  - **Pliki logów z rotacją**:
    - `logs/detect.log` — zdarzenia detekcji (M2)
    - `logs/compare.log` — porównania z minutami przewagi (M3)
    - `logs/app.log` — ogólny log pracy bota
    - `logs/errors.log` — błędy
- **Brak** integracji powiadomień (Telegram/webhook/Discord/SMS).

---

## 5. Przepływ działania (krok po kroku)

```
start
  │
  ├─ M1: weryfikacja klucza + endpointów → log PASS/FAIL
  │
  ├─ M2 (szybka pętla, ~1–2 s): przewidywanie ID → detekcja → T_detect
  │
  ├─ M3 (wolniejsza pętla, ~15–30 s): wyszukiwarka → T_browser
  │
  └─ M3 dopasowuje ID → przewaga[min] → log + tabela w cmd
```

Przykładowa linia z komparatora:

```
[12:30:15] ID=987654321 iPhone 13 256GB | detect=12:29:40 | browser=12:36:55 | przewaga=+7.2 min
[12:30:16] ID=987654322 MacBook Pro M2    | detect=12:28:10 | browser=12:28:10 | przewaga=+0.0 min (miss)
```

---

## 6. Jak będziemy to weryfikować (plan testów)

### Faza 0 — Weryfikacja fundamentów (bez niej nie startujemy dalej)
- [ ] Klucz deweloperski OLX odpowiada (200, nie 401/403) → `PASS/FAIL`.
- [ ] Pobrać próbkę ID z kategorii i potwierdzić, że ID są rosnące/sekwencyjne → czy metoda ID ma sens.
- [ ] Odczyt ogłoszenia po przewidzianym ID zwraca dane szybciej niż wyszukiwarka → pierwszy dowód przewagi.
- **Wynik:** decyzja GO / NO-GO i ewentualny fallback.

### Faza 1 — Detekcja + komparator na żywo
- [ ] Puścić bota na wybranej kategorii (najpierw jedna, np. iPhone).
- [ ] Zbierać pary `(T_detect, T_browser)` przez np. 24–48 h.
- [ ] Zweryfikować, czy przewaga realnie wynosi ok. **10 min** (wartość z poprzedniej wersji) — ile wychodzi teraz.

### Faza 2 — Test „w samopas" (zgodnie z notatkami zlecenia)
- [ ] AI/automatyczny tester z dostępem do strony OLX porównuje nasze wykrycia z realnymi wpisami.
- [ ] Sprawdzenie, czy **nic nie umyka** (czy komparator nie zgłasza ogłoszeń, których my nie wykryliśmy).

### Metryki sukcesu
- Brak 401/403 na kluczu.
- Udział trafień: jak duży % nowych ogłoszeń wykrywamy przez przewidywanie ID.
- Średnia/mediana przewagi w minutach.
- Liczba „miss" (wyszukiwarka pierwsza).
- Liczba fałszywych detekcji (ID przewidziane, ale ogłoszenie nie pasuje do filtra).

---

## 7. Kryteria akceptacji

1. Bot działa jako CLI, logi w cmd + pliki, **zero powiadomień**.
2. Komparator **na bieżąco** pokazuje przewagę w minutach dla każdego dopasowanego ID.
3. Obsługuje 3 zestawy filtrów (iPhone, MacBook, auta ≤12k Mazowsze).
4. Osiąga wykrywanie „przed wyszukiwarką" — średnia przewaga > 0 min.
5. Raport z fazy 0 (czy klucz i metoda ID nadal działają) jest dostarczony jako pierwszy artefakt.

---

## 8. Ryzyka i fallback

| Ryzyko | Objaw | Fallback |
|--------|-------|----------|
| Klucz deweloperski nie działa / ban przy dużej liczbie requestów | 401/403/429 | Bez klucza mamy mniejszy budżet zapytań — zwalniamy interwały, dodajemy jitter i proxy; klucz jest głównie po to, żeby robić dużo requestów bez banów |
| OLX zmienił ID na niesekwencyjne/UUID | nie da się przewidzieć ID | Monitoring wysoko-częstotliwościowy kategorii (polling feed) zamiast przewidywania |
| Endpoint wewnętrzny wymaga podpisu/CSRF | błędy 403 na odczycie po ID | Odwzorować nagłówki/sesję ze strony, ewentualnie headless browser |
| Przewaga spadła do ~0 | wyszukiwarka nie ma już opóźnienia | Zmiana metody na różnicowe porównywanie feedów (szybszy feed vs wolniejszy) |
| Ban/rate-limit IP | 429 / blokada | Jitter, dłuższe interwały, opcjonalnie proxy (jak przy Vinted) |

---

## 9. Kolejność prac

1. **Faza 0** — weryfikator klucza + sondowanie ID (artefakt: raport GO/NO-GO).
2. **M2** — detektor z przewidywaniem ID, logi do `detect.log`.
3. **M3** — komparator z licznikiem minut + tabela w cmd.
4. **M4** — logger, rotacja, finalna forma CLI.
5. **Faza 1–2** — testy na żywo, statystyki przewagi.

---

## 10. Otwarte pytania do klienta

- Czy bot ma **tylko wykrywać i logować**, czy w przyszłości też coś robić z wykrytymi ogłoszeniami (np. alert w CLI, eksport)?
- Czy auta (Mazowsze) i sprzęt Apple mają działać **równolegle** od razu, czy startujemy od jednej kategorii?
- Jakie interwały są akceptowalne (szybsze odpytywanie = większe ryzyko rate-limitu)?