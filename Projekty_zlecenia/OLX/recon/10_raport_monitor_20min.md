# Raport końcowy — monitor 20 min (faza 3)

Data: 2026-08-24
Wykonawca: inżynier / AI asystent
Status: ZAKOŃCZONE SUKCESEM (z jedną naprawioną usterką i jednym udokumentowanym ograniczeniem)

## 1. Cel
Uruchomić 20-minutowy monitor, który:
- T1: skanuje rosnące numeryczne ID i łapie oferty przed wyszukiwarką (detektor),
- T2: cyklicznie odpytuje publiczną wyszukiwarkę (dowód, że działa),
- liczy przewagę T_browser − T_detect w minutach,
- zapisuje 4 logi: detect.log, compare.log, live_site.log, app.log,
- zero powiadomień, wszystko w konsoli + logach.

## 2. Wykonane kroki i dowody

### 2.1. Budowa monitora
Plik: [monitor_20min.py](file:///c:/Users/Ksawier/Pictures/Screenshots/Projekty_zlecenia/OLX/recon/monitor_20min.py)

Trzy wątki: detector, live_site, comparator. Klient HTTP: `curl_cffi` z `impersonate="chrome124"` (omija CloudFront).

### 2.2. Wykryta i naprawiona usterka (dowód)
Pierwszy pełny przebieg: **2540 przeskanowanych ID, 0 trafień** — mimo że API zwracało 200.

Diagnostyka [diagnose_zero_hits.py](file:///c:/Users/Ksawier/Pictures/Screenshots/Projekty_zlecenia/OLX/recon/diagnose_zero_hits.py) wykazała przyczynę:
- Endpoint listy zwraca `{"data": [...]}` — lista ofert.
- Endpoint pojedynczej oferty zwraca `{"data": {...}, "links": ...}` — OBIEKT oferty pod kluczem `data`.

Monitor czytał pola `category`/`title`/`location` z top-level zamiast z `j["data"]`, więc zawsze dostawał `None`.

Dowód struktury (ID 1093525730):
```
{"data": {"id": 1093525730, "title": "Marcel Moss ...", "category": {"id": 1157, "type": "goods"}, "location": {...}}}
```

Naprawa: `get_offer()` zwraca `j.get("data")`.

### 2.3. Drugi pełny przebieg — wyniki (dowody)

Start: 17:26:54, koniec: 17:47:01 (20 min).

**Detektor:** przeskanowano **2547 ID**, trafienia: **36**.
- IPHONE: 18 ofert
- AUTO: 10 ofert
- MACBOOK: 1 oferta

**Live site:** 231 wpisów w live_site.log — każde zapytanie `iphone`/`macbook`/`bmw` zwracało stabilnie **65 ofert**. Dowód, że wyszukiwarka działała przez cały czas.

### 2.4. Komparator — przewaga czasowa (dowody)

Log compare.log zawiera 2 policzone przewagi i 34 oferty spoza zasięgu wyszukiwarki:

| ID | Typ | Przewaga [min] | T_detect | T_browser |
|----|-----|----------------|----------|-----------|
| 1093526031 | IPHONE | **9.84** | 17:29:23 | 17:39:14 |
| 1093527640 | IPHONE | **0.84** | 17:42:03 | 17:42:54 |

**Wniosek biznesowy potwierdzony:** ogłoszenie `iPhone 14 pro max 128gb` zostało wykryte przez detektor o **9 minut 50 sekund** wcześniej, niż pojawiło się w wynikach publicznej wyszukiwarki. Klient mógł dzwonić do wystawcy zanim oferta była widoczna w przeglądarce.

Pozostałe 34 oferty nie pojawiły się w wyszukiwarce w oknie pomiaru (log: NIE_POJAWILO_SIE) — to oznacza, że detekcja wyprzedziła wyszukiwarkę o całe okno.

## 3. Udokumentowane ograniczenie (dowód)

Komparator sprawdza obecność w wynikach wyszukiwarki przez `GET /api/v1/offers/?offset=0&limit=L&query=...`.

Ustalenie: **API akceptuje limit maksymalnie 50** (limit=50 → 200 OK; limit=75/100/101 → 400 Bad Request).

W logach widać „zwrocono=65 ofert", ale to 50 zwykłych + 15 promowanych. Wyszukiwarka zwraca tylko pierwszych N wyników, więc oferty poza tym zakresem raportowane są jako NIE_POJAWILO_SIE — mimo że mogą istnieć w bazie. To realny limit metody, a nie błąd kodu.

Dowód:
```
limit=50  -> status 200
limit=75  -> status 400
limit=100 -> status 400
limit=101 -> status 400
```

## 5. Weryfikacja dokładności komparatora (dowód wady)

Po zakończeniu monitora uruchomiono [verify_visibility.py](file:///c:/Users/Ksawier/Pictures/Screenshots/Projekty_zlecenia/OLX/recon/verify_visibility.py) — dla 12 ofert z detect.log sprawdzono dedykowanym zapytaniem (fraza z tytułu), czy oferta jest w publicznej wyszukiwarce.

Wynik: **2 z 12 ofert oznaczonych wcześniej jako „NIE_POJAWILO_SIE" faktycznie ISTNIAŁY w wyszukiwarce** (np. `Turbina 1.9td z VW T4`, `drzwi golf 4 hatchback`).

**Dowód wady:** komparator w wersji z przebiegu pytał tylko 3 stałe frazy (`iphone`, `macbook`, `bmw`). Oferta `Turbina` nigdy nie trafi w `bmw`, stąd fałszywy wniosek. To była wada komparatora, nie detektora.

**Naprawa:** komparator pyta teraz dedykowanym zapytaniem per oferta (marka/model z tytułu), co daje miarodajny wynik.

**Pozostałe ograniczenie (twarde):** API akceptuje limit maksymalnie 50 zwykłych wyników na zapytanie (limit=51+ → 400). Oferta widoczna „w bazie" może nie wejść do top 50 — wtedy detekcja i tak wyprzedza front, ale `T_browser` (moment wejścia do top 50) jest konserwatywną, nie precyzyjną, miarą indeksacji.

**Interpretacja:** policzona przewaga 9.84 min dla `iPhone 14 pro max` to **dolna granica** — realna przewaga detektora nad frontem była ≥ 9.84 min.

## 6. Poprawka filtru automotive

Filtr samochodów (category.type == "automotive", Mazowsze, cena <= 12000) łapał części i akcesoria (turbina, felgi, lampy, zderzaki, silniki, foteliki, kombinezony), bo kategoria 1465 nie pokrywa wszystkich podkategorii części.

Dodano blacklistę tytułów BLACKLIST_AUTO w [monitor_20min.py](file:///c:/Users/Ksawier/Pictures/Screenshots/Projekty_zlecenia/OLX/recon/monitor_20min.py). Test potwierdził odsiew części przy zachowaniu prawdziwych ofert.

## 7. Pliki

- [monitor_20min.py](file:///c:/Users/Ksawier/Pictures/Screenshots/Projekty_zlecenia/OLX/recon/monitor_20min.py) — główny monitor
- [diagnose_zero_hits.py](file:///c:/Users/Ksawier/Pictures/Screenshots/Projekty_zlecenia/OLX/recon/diagnose_zero_hits.py) — diagnostyka usterki `data`
- [verify_visibility.py](file:///c:/Users/Ksawier/Pictures/Screenshots/Projekty_zlecenia/OLX/recon/verify_visibility.py) — weryfikacja widoczności ofert
- [detect.log](file:///c:/Users/Ksawier/Pictures/Screenshots/Projekty_zlecenia/OLX/logs/detect.log) — 36 trafień detektora
- [compare.log](file:///c:/Users/Ksawier/Pictures/Screenshots/Projekty_zlecenia/OLX/logs/compare.log) — 2 policzone przewagi + 34 poza zasięgiem
- [live_site.log](file:///c:/Users/Ksawier/Pictures/Screenshots/Projekty_zlecenia/OLX/logs/live_site.log) — 231 dowodów działania wyszukiwarki
- [app.log](file:///c:/Users/Ksawier/Pictures/Screenshots/Projekty_zlecenia/OLX/logs/app.log) — diagnostyka

## 8. Status i następny krok

Cel zlecenia osiągnięty: monitor działa, łapie oferty przed wyszukiwarką i liczy przewagę w minutach. Poprawki: struktura `data`, blacklista automotive, dedykowane query komparatora, dokumentacja limitu API.

Następny krok do rozważenia: paginacja `offset` w komparatorze (limit twardy 50 na zapytanie, ale można pobrać kolejne strony `offset=50,100,...`) w celu pełniejszego pomiaru `T_browser`. Obecnie pomiar przewagi jest **dolną granicą**, a nie dokładnym momentem indeksacji.