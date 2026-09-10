# DZIENNIK SESJI 2026-08-24 — wszystko, czego nie ma w plikach technicznych

Data: 2026-08-24
Autor: asystent AI (praca z użytkownikiem + weryfikacje własne/Gemini)

## 0. Cel nadrzędny sesji

Użytkownik zlecił projekt bota OLX, który:
- wyprzedza wyszukiwarkę metodą przewidywania rosnących numerycznych ID,
- sam się weryfikuje (porównuje detekcję ID z wynikami wyszukiwarki),
- liczy przewagę w minutach (T_browser − T_detect),
- zero powiadomień — wszystko w logach + konsola (cmd).

Pod koniec sesji użytkownik zażądał:
1. ostrych testów "bez zaufania" — czy detektor naprawdę nie pomija i nie łapie śmieci,
2. zbadania, czy status partnera / klucz API chroni przed banem,
3. **udokumentowania WSZYSTKIEGO, co było w tej sesji, a czego nie ma w plikach technicznych.**

Niniejszy plik jest punktem 3.

---

## 1. OŚ CZASU FAKTYCZNYCH DECYZJI I ODKRYĆ

### 1.1. Pierwszy przebieg monitora — 0 trafień (bug struktury)
- Uruchomiono monitor_20min.py (wersja synchroniczna, limit 50, kategoria `type=="automotive"`).
- Wynik: 2540 przeskanowanych ID, **0 trafień** mimo poprawnych odpowiedzi 200.
- Diagnoza (diagnose_zero_hits.py): endpoint pojedynczej oferty zwraca obwiednię `{"data": {...}, "links": ...}`, a monitor czytał pola z top-level.
- Naprawa: `get_offer()` zwraca `j.get("data")`.

### 1.2. Kategorie "twarde" — dowód sondą, nie wiarą
- Zdecydowano NIE ufać kategoriom z RECON, tylko je zweryfikować na żywo.
- Sonda probe_classifier_truth.py / probe_cat_truth.py dała:
  - 2298 = 100% iPhone (65/65)
  - 3102 = 100% MacBook (65/65)
  - 183 = całe auta osobowe (64/64)
  - czesci/akcesoria moto = 1399, 1465, 1385, 4488
- Kluczowa zmiana: filtr `type=="automotive"` → twardy `cat_id=183`. To wyeliminowało turbiny, felgi, lampy, dywaniki.

### 1.3. Limit API i paginacja — udowodnione, nie założone
- limit=50 max (51→400), offset max ~1000, `visible_total_count` realnie ~142k dla "iphone", ale `total_elements` twardo 1000.
- Wniosek biznesowy: wyszukiwarka NIE pokazuje wszystkiego; detektor ID widzi więcej.

### 1.4. Komparator — od fałszywych "NIE_POJAWILO_SIE" do precyzji
- Wada v1: pytał tylko 3 stałe frazy (iphone/macbook/bmw) → oferta "Turbina VW" nigdy nie trafi w "bmw".
- Wada v2: pytał "iphone" (22k wyników) → świeża oferta nie wchodziła do top 50.
- Naprawa: precyzyjna fraza z tytułu (pierwsze 4 znaczące słowa) + twarda kategoria + offset 0/50/100.
- Weryfikacja verify_visibility.py: 2 z 12 "NIE_POJAWILO_SIE" faktycznie BYŁY w wyszukiwarce (dowód wady).

### 1.5. Tempo kreacji ID — pomiar zamiast zgadywania
- measure_creation_rate.py: kreacja ~2.19 ID/s (134 nowe w 61s).
- Sekwencyjny skaner ~2.37 ID/s → zapas tylko 0.18 ID/s (ledwo nadąża).
- Asynchroniczny skaner (test_async_scan.py): **57 ID/s bez blokady** → 25x zapas.

### 1.6. Krytyczny bug "ucieczka w przyszłość" (zgłosiło Gemini)
- W pętli asynchronicznej `oid += batch_size` przy samych 404 powodował skok do przodu i pomijanie nowych ofert.
- Naprawa: sliding window — head przesuwa się TYLKO do `max_200+1`, przy 404 czeka i ponawia.

### 1.7. Krytyczny bug "brak retry" (zgłosiło Gemini)
- Przy timeout `-1` head przeskakiwał nad nieudanym ID, bezpowrotnie gubiąc ofertę.
- Naprawa: retry 2× z backoffem w `_scan_batch` + blokada head przy `-1` w fazie 2.

### 1.8. Weryfikacja przeglądarką (Playwright)
- Gemini słusznie wytknęło mój błąd: "20 ofert" to był limit JSON-LD (SEO), a nie DOM.
- Po akceptacji OneTrust (button#onetrust-accept-btn-handler) DOM ma **52 karty** `div[data-cy='l-card']`.
- Frontend NIE używa `/api/v1/offers/` do pierwszej porcji — oferty renderowane server-side w HTML.
- Wniosek: nasz detektor (API po ID) widzi oferty wcześniej niż frontend.

### 1.9. Test klucza partnerskiego
- OAuth działa: token client_credentials, partner_code=4420, scope=v2 read write.
- `/api/partner/adverts` (nawet z nagłówkiem Version) → `Invalid user ID in token`.
- Endpoint partnerski to zarządzanie WŁASNYMI ogłoszeniami, nie wyszukiwarka cudzych.
- **Detektor w ogóle nie używa klucza partnerskiego.** Skanuje publiczne `/api/v1/offers/{id}/`.

### 1.10. Ostry test: token vs brak tokenu (na żądanie użytkownika)
- stress_token_vs_no_token.py: 200 interleaved zapytań (100 bez tokenu, 100 z tokenem).
- Wynik: oba scenariusze identyczne — **0 blokad 403/429**, ok=78/200 w obu.
- Wniosek: **token partnerski NIE daje żadnej ochrony/limitu na publicznym API.** Jest dla detektora bezużyteczny.

---

## 2. ODPOWIEDZI NA KONKRETNE PYTANIA UŻYTKOWNIKA (werdykty)

| Pytanie | Werdykt | Dowód |
|---|---|---|
| "Dasz rękę uciąć, że detektor nie pomija nic co chcemy?" | NIE na 100%, ale po naprawach bardzo blisko | 2 krytyczne bugi naprawione (ucieczka, retry) |
| "Detektor nie daje nic poza filtrem?" | NIE na 100% | 2 śmieci wpadły w 20-min; blacklista tytułowa nie jest kompletna |
| "Mamy realną przewagę co najmniej 1 minuty?" | NIE gwarantowana | świeże oferty: 5.53–16.61 min; ale 0.05 min to artefakt startu |
| "Ten 0.05 wszedł od razu jak odpaliłem bota?" | TAK, potwierdzone | created 18:39 vs start bota 18:46 |
| "Nie ma bana bo mamy oficjalny klucz i status partnera?" | FAŁSZ | token nie daje ochrony; detektor nie używa klucza |
| "Po chuj nam ten jebany status partnera i klucz?" | Bezużyteczny dla detektora | /api/partner/adverts = Invalid user ID; stress test 0 różnicy |

---

## 3. ZBIORCZA LISTA BŁĘDÓW / POPRAWEK W SESJI

1. Bug struktury JSON (top-level vs `data`) → naprawa get_offer.
2. Kategoria automotive ogólnikowa → kategoria twarda 183.
3. Parsowanie ceny "12 000" → _parse_price z normalizacją.
4. Marka "Sprzedam Opel" → _pick_brand ze stop-listą.
5. Komparator 3 frazy → precyzyjna fraza + kategoria + paginacja.
6. Detektor synchroniczny 2.37 ID/s → asynchroniczny 57 ID/s.
7. Ucieczka w przyszłość (oid += batch_size) → sliding window.
8. Brak retry przy -1 → retry 2× + blokada head.
9. Blacklista tytułowa niekompletna → dodano FaceID/slab/bez ekranu/uszkodzone.

---

## 4. CO NADAL NIE DZIAŁA / RYZYKA (szczera lista)

1. **Brak rotacji IP/proxy.** Ostre testy 200 zapytań nie wywołały blokady, ale 24/7 przy 30 ID/s prędzej czy później tak. Token tego nie rozwiązuje (dowiedzione).
2. **Blacklista tytułowa nigdy nie będzie 100%.** Klasyfikator oparty o tytuł przepuszcza nietypowe śmieci.
3. **Brak trybu 24/7.** Obecny monitor to jednorazowy przebieg z re-seedem; nie ma pętli ciągłej odpornej na bany.
4. **Porównanie detektor vs przeglądarka wciąż nie w pełni wiarygodne** (porównanie po tytułach dało 1/52 — trzeba diff po ID numerycznym z JSON-LD lub URL).
5. **Bot produkcyjny nie istnieje.** To nadal skrypty badawcze w recon/.

---

## 5. PLIKI UTWORZONE W TEJ SESJI (mapa)

recon/:
- monitor_20min.py — główny monitor (wielokrotnie przebudowywany)
- diagnose_zero_hits.py — diagnostyka 0 trafień (bug JSON)
- verify_visibility.py — weryfikacja widoczności ofert w wyszukiwarce
- test_classifier.py — 29 testów jednostkowych (PASS)
- probe_classifier_truth.py / probe_cat_truth.py — sondy kategorii
- measure_creation_rate.py — pomiar tempa kreacji ID
- test_async_scan.py — dowód 57 ID/s async
- probe_async_zero_hits.py — diagnostyka rozkładu kategorii w oknie
- probe_browser.py / probe_browser_block.py — przechwytywanie requestów frontendu
- verify_browser_vs_api.py / verify_detector_vs_browser.py — diff z przeglądarką
- probe_dom_cards.py — dowód 52 kart po OneTrust
- stress_token_vs_no_token.py — ostry test klucza vs publiczne API
- test_api_klucz.py / test_partner_adverts.py — testy klucza partnerskiego

recon/*.md — raporty 00–12 (dokumentacja techniczna).

logs/ — detect.log, compare.log, live_site.log, app.log, browser_requests.jsonl, browser_page.html, browser_cards.png, browser_offers.json.

---

## 6. WAŻNE WARTOŚCI DOWODOWE

- Tempo kreacji OLX: ~2.19 ID/s (szczyt, 2026-08-24 ~18:50).
- Maks. tempo async bez blokady: 57 ID/s.
- Kategorie twarde: 2298 iPhone, 3102 MacBook, 183 auta; czesci: 1399/1465/1385/4488.
- Limit API: limit=50 max; offset max 1000; visible_total_count dla iphone ~142k.
- DOM przeglądarki: 52 karty po OneTrust (JSON-LD to tylko 20 dla SEO).
- Przewagi świeżych ofert: 5.53–16.61 min (20-min przebieg).
- Klucz partnerski: OAuth OK, ale /api/partner/adverts = Invalid user ID; 0 ochrony na publicznym API.

---

## 7. CZEGO UŻYTKOWNIK MOŻE SIĘ SPODZIEWAĆ DALEJ

1. Monitor łapie świeże oferty iPhone/MacBook/auta z przewagą zwykle >5 min.
2. Przy bardzo małym ruchu (środek dnia) mogą być okna 0 trafień — to nie awaria, tylko brak ofert w kategoriach.
3. Publiczne API toleruje nasze obecne tempo, ale każdy długi skan z jednego IP kończy się banem — trzeba rotacji proxy przed trybem 24/7.
4. Klasyfikator będzie wymagał okresowego dodawania słów do blacklisty, bo zawsze trafi się nowy typ śmiecia.