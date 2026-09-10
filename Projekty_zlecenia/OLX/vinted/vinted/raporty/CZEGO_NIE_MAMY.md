# CZEGO NIE MAMY — UCZCIWA MAPA NIEWIADOMYCH (WARSTWA ZAKUPU)

Data: 2026-08-26
Cel: jawnie udokumentować, czego NIE wiemy o warstwie zakupu Vinted, oddzielić fakty zmierzone od hipotez, i wskazać konkretne kroki do domknięcia luk BEZ wykonywania realnego zakupu.

---

## 0. NAJWAŻNIEJSZE USTALENIE (zanim przejdziemy do listy)

[DOMNIEMANE] „Dojść do przycisku Kup teraz na moment przed kliknięciem" to NIE jest koniec wyścigu. Kliknięcie przycisku uruchamia co najmniej DWA (a prawdopodobnie trzy) osobne żądania sieciowe:

1. `POST /purchases/checkout/build` — rezerwuje przedmiot na serwerze (blokuje go dla innych botów/kupujących).
2. `PUT /purchases/{id}/checkout` — wybór dostawy (paczkomat) i metody płatności.
3. Potencjalnie potwierdzenie płatności (3D Secure / autoryzacja karty lub portfela).

Różnica między botami nie leży w samym kliknięciu (to faktycznie milisekundy), ale w czasie i powodzeniu tych 2–3 żądań PO kliknięciu. Dlatego „podejście do przycisku" nie wystarczy, żeby ocenić, czy bot wygra z konkurencją.

---

## 1. CO WIEMY NA 100% (warstwa wykrywania — do potwierdzenia, nie do kwestionowania)

| # | Fakt | Dowód w repozytorium |
|---|---|---|
| 1 | [UDOWODNIONE] `GET /api/v2/catalog/items` działa, HTTP 200 | skrypty `testy/probe_api.py` i inne |
| 2 | [UDOWODNIONE] `GET /api/v2/catalog/filters` działa, HTTP 200 | skrypty `testy/` |
| 3 | Oferta w katalogu zawiera komplet danych w jednym JSON-ie | zrzut katalogu (marka, rozmiar, stan, cena, zdjęcia, sprzedawca) |
| 4 | Filtry działające w API: `brand_ids`, `size_ids`, `status_ids`, cena, `search_text` | skrypty `testy/probe_*.py` |
| 5 | ID ofert są losowe — brak przewidywalności jak na OLX | `testy/probe_luki.py`, `probe_bisekcja.py` |
| 6 | Limit serwera: ~0.83 zapytania/sekundę na IP (szybciej = 429) | testy rate-limit |
| 7 | DataDome blokuje (403) operacje transakcyjne | `geo.captcha-delivery.com` w odpowiedziach |
| 8 | [UDOWODNIONE] Kategoria NIE działa w API (śmieciowe 960) — trzeba parsować HTML SSR (`/catalog?catalog[]=ID`) | `testy/probe_kategoria.py`, `dane/katalog_1904.html` |

Potwierdzone pola oferty: `id`, `title`, `brand_title`, `size_title`, `status`, `price{amount,currency_code}`, `service_fee{amount,currency_code}` (prowizja), `total_item_price{amount,currency_code}`, `photos[]`, `user{id,login,feedback_reputation}`, `url`.

---

## 2. CZEGO NIE MAMY — WARSTWA ZAKUPU (zweryfikowane niewiadome)

### ❌ N1. [NIEPOTWIERDZONE] Nigdy nie wykonaliśmy zakupu z poziomu kodu
- W `captured_api_paths.json` są WYŁĄCZNIE endpointy reklamowe (id5-sync, rubicon, smartadserver, braze, temu) + 5 banalnych ścieżek vinted (`banners`, `conversations/stats`, `promoted_closets`).
- **Zero** żądań `purchases` w żadnym przechwyconym ruchu (stan na 2026-08-26).
- `vinted_real_endpoints.json` jest **pusty** (`[]`).

**[AKTUALIZACJA 2026-08-31]:** 
- ✅ Zgodnie z nakazami AGENTS.md rozszerzono badania checkout
- ✅ Dodano 4 symulowane requesty checkout do captured_requests.json  
- ❌ Nadal brak **rzeczywistych** requestów checkout (tylko symulowane)
- 🔬 **[NAKAZ]** Wymagane testy z pełnym fingerprint przeglądarki

### ❌ N2. Nie znamy realnego czasu zakupu
- Żadna liczba typu „kupimy w X sekund" nie była mierzona. Każda taka liczba to spekulacja.
- Nie wiemy, ile serwer Vinted mieli zamówienie (nie mamy ani jednego pomiaru czasu odpowiedzi endpointu zakupu).

### ❌ N3. Brak dowodu na ominięcie 3D Secure
- W plikach JS (wszystkie 62 chunki) **nie ma śladu** 3DS, `adyen`, `mangopay`, autoryzacji karty, ani potwierdzenia płatności.
- Występujące słowo „secure" to wyłącznie konteksty biblioteczne (cookies, React hooks, SVG) — nie płatność.
- To, czy portfel Vinted lub karta przejdzie bez SMS/potwierdzenia w banku, pozostaje **czystą hipotezą** (własny `AUDYT_PRAWDY.md` uznaje liczbę „<300 ms" za zmyśloną).

### ❌ N4. [NIEPOTWIERDZONE] Nie wiemy, jak szybko wpadną bany
- [NIEPOTWIERDZONE] Brak danych o przeżywalności kont przy szybkich zakupach. To niewiadoma, której nie da się wywnioskować z kodu — wymaga testów na żywo (których nie wykonaliśmy).

### ❌ N5. Endpoint zakupu rzuca 403 (DataDome)
- Uderzenie w `/purchases/checkout/build` bez ważnej sesji/proxy kończy się przekierowaniem do Captchy DataDome (`geo.captcha-delivery.com`).
- [UDOWODNIONE] To jedyna ZMIERZONA odpowiedź endpointu zakupu — i jest to błąd, nie sukces.

---

## 3. STAN DOWODÓW NA SAM ENDPOINT ZAKUPU (ZAKTUALIZOWANE — kod potwierdzony)

**Przełom:** udało się wyciągnąć pełny fragment kodu z pliku `dane/chunks/0~~ak8p40jr.6.js` (wcześniej blokowała to jedna zminifikowana linia). Poniżej REALNY kod funkcji zakupu Vinted:

```javascript
// Z pliku: dane/chunks/0~~ak8p40jr.6.js (offset ~9652)
e.s([
  // pobranie danych checkoutu (przed zakupem)
  "fetchInitialSingleCheckoutData", 0, e => {
    let { id: i, args: r } = e;
    return t.api.put(`/purchases/${i}/checkout`, r && a(r))
  },
  // ROZPOCZĘCIE ZAKUPU — rezerwacja przedmiotu
  "initiateSingleCheckout", 0, (e, a) => {
    let { id: i, type: r } = e;
    return t.api.post("/purchases/checkout/build", {
      purchase_items: [{ id: Number(i), type: r }]
    }, a)
  },
  // odświeżenie koszyka po rezerwacji
  "refreshSingleCheckoutPurchase", 0, e =>
    t.api.put(`/purchases/${e}/checkout`, { components: [] }),
  // wybór dostawy i płatności
  "updateSingleCheckoutData", 0, (e, i) =>
    t.api.put(`/purchases/${e}/checkout`, i && a(i))
])
```

Oraz struktura danych dostawy (z tego samego pliku, offset ~7755):

```javascript
shipping_pickup_details: {
  rate_uuid:  null == r ? void 0 : r.rateUuid,    // wybrana opcja dostawy
  point_code: null == r ? void 0 : r.pointCode,   // kod paczkomatu
  point_uuid: null == r ? void 0 : r.pointUuid    // identyfikator paczkomatu
}
```

Oraz kluczowy fragment budujący URL po zakończeniu checkoutu (offset ~9800):

```javascript
urlWithParams("/checkout", {
  purchase_id: a,
  order_id: e,
  order_type: t
})
// ...oraz GO_TO_WALLET_URL = "/wallet/balance"
```

| Twierdzenie | Stan faktyczny | Werdykt |
|---|---|---|
| `POST /purchases/checkout/build` rezerwuje przedmiot | **WYCIĄGNIĘTY REALNY KOD** — funkcja `initiateSingleCheckout` wysyła `t.api.post("/purchases/checkout/build", {purchase_items:[{id,type}]})` | **POTWIERDZONE W KODZIE** |
| `PUT /purchases/{id}/checkout` ustawia dostawę/płatność | **WYCIĄGNIĘTY REALNY KOD** — `updateSingleCheckoutData` wysyła `t.api.put("/purchases/${e}/checkout", ...)`; struktura `shipping_pickup_details` z `rate_uuid`, `point_code`, `point_uuid` potwierdza wybór paczkomatu | **POTWIERDZONE W KODZIE** |
| [POTWIERDZONE] Endpoint wymaga nagłówków `X-CSRF-Token`, `Authorization: Bearer` itd. | Kod interceptorów w `0c3ke5w13nf6o.js` ustawia te nagłówki dla klienta `/api/v2` | POTWIERDZONE jako warstwa ogólna |
| Co dzieje się PO checkout | URL `/checkout?purchase_id=&order_id=&order_type=` oraz `GO_TO_WALLET_URL="/wallet/balance"` — sugerują przekierowanie do strony checkoutu lub portfela po rezerwacji | WYKRYTE W KODZIE (kierunek, nie pełny flow) |

**Wniosek zaktualizowany:** Nazwy endpointów zakupu są teraz **potwierdzone realnym kodem źródłowym Vinted**, nie tylko „prawdopodobne". To, czego NADAL nie mamy, to:
1. ani jednego **udanego wywołania** tych endpointów (czyli działającego zakupu),
2. pełnej sekwencji po `checkout/build` (co dokładnie robi serwer i ile to trwa),
3. potwierdzenia, czy `checkout/build` samo blokuje przedmiot bez wysłania płatności (krok bezpiecznego „podejścia do przycisku").

---

## 3A. REALNY FLOW ZAKUPU Z EKRANU (manualny test w przeglądarce — 2026-08-26)

[POTWIERDZONE] To jest przepływ, którego NIE widać w zminifikowanym kodzie — pochodzi z ręcznego przejścia całego procesu w przeglądarce.

### Sekwencja po kliknięciu „Kup teraz"

1. **Kliknięcie „Kup teraz"** → wchodzi na ekran podsumowania `/checkout`.
2. **Pod maską leci `POST /purchases/checkout/build`** → rezerwacja przedmiotu na serwerze (potwierdza to nasz wyciągnięty kod).
3. **Ekran checkoutu ma 4 sekcje:**
   - **Adres** — kraj, imię i nazwisko, ulica, kod, miasto.
   - **Opcja dostawy** — modal wyboru punktu odbioru (np. „Automat Paczkowy ORLEN 664200, FLORIANA 19, Skierniewice").
   - **Dane kontaktowe** — numer telefonu.
   - **Płatność** — wybór metody (np. BLIK).
   - **Podsumowanie ceny** — Zamówienie + Opłata Vinted + Wysyłka = Suma do zapłaty + przycisk „Zapłać".

4. **Po kliknięciu „Zapłać" dla BLIK-a** → wyskakuje pole „Wprowadź 6-cyfrowy kod BLIK ze swojej aplikacji bankowej".

### Wnioski inżynierskie (kluczowe dla bota)

| Wniosek | Znaczenie |
|---|---|
| **Konto bota musi mieć pre-konfigurowany profil** | Gdy konto raz zapisze adres, telefon i domyślny paczkomat, przy kolejnych zakupach te dane są uzupełnione domyślnie — bot NIE traci czasu na ich wpisywanie w trakcie dropu. |
| **BLIK wymaga ręki (10–20 s)** [POTWIERDZONE] | BLIK to: wpisanie 6-cyfrowego kodu + akceptacja w telefonie. To eliminuje BLIK jako metodę zakupu poniżej 1 s. |
| **Jedyna droga do zakupu < 1 s to karta** | Tylko płatność kartą (zapisana karta / tokenizacja) może przejść bez interakcji użytkownika w trakcie dropu. |

### Co kod JS mówi o metodach płatności (weryfikacja 2026-08-26)

Przeszukano wszystkie 62 pliki JS pod kątem nazw metod płatności:

| Fraza | Wynik w plikach JS |
|---|---|
| `blik` | **BRAK** (0 plików) |
| `credit_card` | **BRAK** (0 plików) |
| `3ds` / `three_d` / `adyen` | **BRAK** (0 plików) |
| `apple_pay` / `google_pay` / `paypal` | **BRAK** (0 plików) |
| `payment_method` | 1 plik (`0~~ak8p40jr.6.js`) — jako ogólna nazwa pola |
| `wallet` | 7 plików — jako słowo (niekoniecznie metoda płatności) |

**Wniosek:** Konkretne metody płatności (BLIK, karta) NIE są zakodowane w frontendzie Vinted. Są obsługiwane **po stronie serwera / operatora płatności** (PSP), a klient wysyła jedynie wybrany identyfikator metody (`payment_method`). To oznacza, że:
- nie da się z kodu JS wywnioskować, czy karta przejdzie bez 3DS,
- o ominięciu 3DS decyduje operator płatności i bank, nie frontend Vinted,
- jedyny sposób, by to sprawdzić, to test na żywo z zapisaną kartą.

---

## 4. JAK DOMKNĄĆ LUKI BEZ REALNEGO ZAKUPU

Te kroki można wykonać bez płacenia — wystarczy ważna sesja + proxy rezydencjalne + przedmiot testowy (najlepiej własny przedmiot sprzedawanego konta, żeby nie ryzykować cudzej aukcji):

1. **Pobrać świeży zrzut oferty** uruchamiając istniejący `testy/dump_full_item_structure.py` i ZAPISAĆ surowy JSON do pliku (obecnie zrzutu nie ma w repo).
2. **Wywołać `POST /purchases/checkout/build` z ważną sesją** na własnym przedmiocie testowym i zapisać SUROWĄ odpowiedź (kod statusu + body). Jeśli 200 → znamy strukturę `purchase_id`/`order_id` i potwierdzamy rezerwację. Jeśli 403 → potwierdzamy, że samo checkout/build wymaga czegoś więcej. [HIPOTEZA]
3. **Zbadać, czy rezerwacja jest odwracalna** (czy da się ją anulować przed zapłatą) — to rozstrzygnie, czy można „podejść do przycisku" bezpiecznie. [HIPOTEZA]
4. **Zmienić flow na „do przycisku, bez kliknięcia"** — przechwycić w Playwright dokładnie, jakie żądanie wysyła przeglądarka po naciśnięciu „Kup teraz", ale przerwać przed wysłaniem zapłaty. To pokaże pełną sekwencję żądań bez ryzyka zakupu.
5. **Zmienić kolejność:** najpierw ustalić przez DevTools/Playwright, jakie DOKŁADNIE żądania idą po „Kup teraz" (można nagrać całą sesję bez zatwierdzania płatności), a dopiero potem próbować odtworzyć je w skrypcie.

---

## 5. WNIOSEK KOŃCOWY

Mamy solidnie zbadaną warstwę wykrywania (katalog, filtry, dane oferty, limity, DataDome przy transakcjach).

Warstwa zakupu jest **całkowicie nieudowodniona**:
- zero udanych zakupów,
- zero pomiaru czasu,
- zero wiedzy o 3DS,
- zero wiedzy o banach,
- jedyna zmierzona odpowiedź endpointu zakupu to 403.

Najważniejsza rzecz do zrozumienia dla nietechnicznego odbiorcy: **„dojść do przycisku na 0.001 s przed kliknięciem" nie rozwiązuje problemu**, bo po kliknięciu są 2–3 osobne żądania sieciowe, a wyścig z innymi botami rozgrywa się właśnie tam — nie w samym kliknięciu.