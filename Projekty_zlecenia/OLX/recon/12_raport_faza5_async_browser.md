# Raport fazy 5 — asynchroniczny detektor + weryfikacja z przeglądarką

Data: 2026-08-24
Status: WYKONANE, DOWODY ZEBRANE

## 1. Odpowiedź na pytanie użytkownika (brutalnie szczera)

Pytanie: "Dasz rękę uciąć, że detektor nie pomija nic co chcemy, nie daje nic poza filtrem, i mamy realną przewagę co najmniej 1 minuty?"

**Odpowiedź: NIE mogę dać 100% gwarancji na żaden z tych 3 punktów. Mogę dać dowody, że znacząco poprawiliśmy każdy z nich.**

### 1.1. "Nie pomija nic co chcemy" — już blisko, ale nie 100%
Naprawiono krytyczną lukę ucieczki w przyszłość (wskazaną przez Gemini):
- Stary kod: `oid += batch_size` po każdym batchu → przy szybkim async skanerze uciekał w przyszłość i omijał nowe ogłoszenia.
- Nowy kod: sliding window — `head` przesuwa się TYLKO do `max_200 + 1`, a przy samych 404 czeka i ponawia to samo okno.

Dowód: pomiar kreacji = 2.19 ID/s. Skaner async = ~30 ID/s (współdzielona sesja). Zapas ~13x.

Pozostałe ryzyko pominięcia: burst importy (Otomoto 100-300 ID naraz) — ale sliding window łapie je po fakcie, bo head nie skacze.

### 1.2. "Nie daje nic poza filtrem" — poprawiono, ale wciąż NIE 100%
W 20-min przebiegu pojawiły się 2 śmieci:
- `Iphone 12 Pro 128GB blad FaceID` (uszkodzony)
- `MacBook Air M1 8GB - Slab / Bez ekranu` (uszkodzony)

**Dodano do blacklisty:** "blad", "błąd", "faceid", "slab", "słab", "bez ekranu", "uszkodzon", "popsuty", "zepsuty".

Klasyfikator wciąż opiera się na tytule — zawsze istnieje szansa na nietypowy śmieć, którego nie ma w blackliście.

### 1.3. "Realna przewaga co najmniej 1 minuty" — NIE, to nieprawda
Zaobserwowane przewagi (20-min przebieg):

| ID | Typ | Przewaga |
|----|-----|----------|
| 1093560556 | MacBook Air 11 | **11.08 min** |
| 1093564440 | iPhone 13 | **5.53 min** |
| 1093560797 | iPhone 14 Pro | **16.61 min** |
| 1093562498 | iPhone 14 Pro Max | **10.97 min** |

Przewaga **bywa** powyżej 1 minuty, ale NIE MA gwarancji:
- W teście 1-min pojawiło się trafienie z przewagą **0.05 min** (50 sekund).
- Zależy to od momentu wejścia oferty do top 50 wyszukiwarki.

**Prawda:** realna przewaga istnieje, zwykle liczona w minutach, ale nie każda oferta ma ≥1 min.

## 2. Nowe dowody z przeglądarki (Playwright)

### 2.1. Frontend renderuje 52 karty (poprawka błędu)
Wcześniej błędnie podałem "20 ofert" — to była wartość z JSON-LD (SEO, limit 20).
Po zaakceptowaniu OneTrust rzeczywisty DOM ma **52 karty** (`div[data-cy='l-card']`).

Dowód:
```
button#onetrust-accept-btn-handler: kliknięto
div[data-cy='l-card']: 52
[data-testid='l-card']: 52
WIDOCZNE karty l-card: 52
```

### 2.2. Frontend NIE używa naszego API do pierwszej porcji
Playwright przechwycił TYLKO 3 requesty API (sentry, categories/config, widgety maze).
Oferty są renderowane server-side w HTML (JSON-LD). To znaczy:
- Nasz detektor (`/api/v1/offers/{id}/`) widzi ogłoszenia wcześniej niż frontend.
- Frontend pokazuje tylko top 52 karty na stronę, nasz detektor skanuje wszystko po ID.

### 2.3. Weryfikacja: przeglądarka 52 karty vs API 65 ofert
API zwraca 65 (50 organic + 15 promowanych), przeglądarka 52 karty.
To są różne warstwy: API = surowe dane, frontend = to co widzi użytkownik po filtracji/SEO.

## 3. Techniczne zmiany w monitor_20min.py

1. **Asynchroniczny detektor** — `AsyncSession` z współdzieloną sesją per batch (~30 ID/s).
2. **Sliding window** — head = max_200 + 1, przy 404 czeka i ponawia (nie ucieka w przyszłość).
3. **Retry błędów sieci (-1)** — po wskazaniu Gemini. Każde ID z timeoutem jest ponawiane 2× z backoffem; head NIE przeskakuje nad nieudanym ID.
4. **Jedno zapytanie na ID** — status + pełna oferta razem (bez podwójnych requestów).
5. **Rozszerzona blacklista iPhone** — FaceID, uszkodzenia, popsute, bez ekranu.
6. **Seed z realnej krawędzi** — faza 1 znajduje granicę 200/404, nie ufa cache'owanej liście.

### 3.1. Naprawiony krytyczny bug retry (dowód Gemini)
Gemini przez Playwright wykazało, że w 20-min przebiegu 3 oferty iPhone (ID 1093560973, 1093561186, 1093562566) zostały pominięte przez timeout `-1` bez ponowienia. Dodano retry w `_scan_batch` i blokadę przesunięcia head przy `-1` w fazie 2.

## 4. Pliki

- [monitor_20min.py](file:///c:/Users/Ksawier/Pictures/Screenshots/Projekty_zlecenia/OLX/recon/monitor_20min.py) — przebudowany detektor
- [test_classifier.py](file:///c:/Users/Ksawier/Pictures/Screenshots/Projekty_zlecenia/OLX/recon/test_classifier.py) — 29 testów PASS
- [probe_dom_cards.py](file:///c:/Users/Ksawier/Pictures/Screenshots/Projekty_zlecenia/OLX/recon/probe_dom_cards.py) — dowód 52 kart
- [measure_creation_rate.py](file:///c:/Users/Ksawier/Pictures/Screenshots/Projekty_zlecenia/OLX/recon/measure_creation_rate.py) — pomiar kreacji 2.19 ID/s
- [test_async_scan.py](file:///c:/Users/Ksawier/Pictures/Screenshots/Projekty_zlecenia/OLX/recon/test_async_scan.py) — dowód 57 ID/s async
- [probe_async_zero_hits.py](file:///c:/Users/Ksawier/Pictures/Screenshots/Projekty_zlecenia/OLX/recon/probe_async_zero_hits.py) — diagnostyka rozkładu kategorii

## 5. Co dalej

1. **Rotacja proxy/sesji** — Gemini słusznie ostrzega przed banem IP przy długim skanowaniu. Bez rotacji IP każdy bot prędzej czy później dostanie 429/challenge.
2. **Ciągły tryb 24/7** — obecny monitor to jednorazowy przebieg. Trzeba zapętlić z re-seedem i odpornością na bany.
3. **Klasyfikator oparty o kategorie, nie tytuły** — już mamy twarde cat_id (183/2298/3102), tytuły to tylko blacklista. To właściwy kierunek.

## 6. Brutalny status

| Element | Stan |
|---------|------|
| Detektor ID | ✅ Działa, async, sliding window |
| Klasyfikator | ⚠️ 29/29 testów, ale blacklista tytułowa nie jest kompletna |
| Komparator przewagi | ✅ Liczy realne przewagi (0.05–16.61 min) |
| Weryfikacja z przeglądarką | ✅ Playwright potwierdził 52 karty i niezależność API |
| Odporność na bany | ❌ Brak rotacji IP — ryzyko krytyczne przy 24/7 |
| Bot produkcyjny | ❌ To wciąż skrypty badawcze, nie złożony moduł |