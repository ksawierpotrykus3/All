# Recon OLX — potwierdzenie sekwencji ID + mapy kategorii API (2026-08-24)

## Dowód 22: Numeryczne ID rośnie globalnie (test skanowania w górę)

Odczyt po kolejnych numerach ID — wszystkie zwróciły oferty:
- `1093493751` → Wiata śmietnikowa (created 15:26:03)
- `1093493800` → Wiata śmietnikowa (created 15:26:03) [ta sama oferta? nie — inna, CID103]
- `1093494000` → Skoda Octavia (created 15:26:52, cross-list otomoto)

Obserwacje:
- ID rośnie w tempie kilkudziesięciu do setek na minutę (cała Polska, wszystkie kategorie).
- Luki między ID wynikają z: szkiców, usuniętych ofert, oraz tego, że ID jest globalne (wszystkie kategorie + cross-listy otomoto + firmy).
- **Metoda skanowania działa:** bierzemy max ID, skanujemy w górę co 1, odczytujemy `GET /api/v1/offers/{id}/`. Trafienie = 200 z danymi, pudło (nieistniejące ID) = pewnie 404 (do potwierdzenia).

## Dowód 23: Mapa category.id (API) vs CID (URL)

| Kategoria | CID (URL) | category.id (API JSON) | type |
|-----------|-----------|------------------------|------|
| Samochody osobowe | 5 | **203** | automotive |
| Telefony | 99 | **2912** | electronics |
| Moda (spodenki) | 87 | 2940 | goods |
| Moda (bluzka) | 88 | 2464 | goods |
| Dom i Ogród (pompa) | 628 | 1698 | house_and_garden |
| Wiata (CID103) | 103 | 2969 | goods |

**Kluczowe dla bota:**
- Auta → filtruj `category.id == 203`
- Telefony (smartfony) → filtruj `category.id == 2912`
- MacBooki (laptopy) → do ustalenia (laptopy to CID?, w API electronics)

## Dowód 24: Cross-listy otomoto są oznaczone

Offer cross-list (Skoda Octavia) ma:
- `"partner":{"code":"otomoto_pl_form"}`
- `"external_url":"https://www.otomoto.pl/..."`
- `"business":true`, user.name="Otomoto"

**Filtr bota:** odrzucaj oferty z `partner.code == "otomoto_pl_form"` (to nie są oferty natywne OLX, klient ich nie chce — pojawiają się z opóźnieniem i są duplikatami).

## Dowód 25: Struktura cen i parametrów w JSON

- Cena: `params[].key=="price"` → `value.value` (liczba) np. 49900
- Rok: `params[].key=="year"` → `value.label` "2019 "
- Paliwo: `params[].key=="petrol"` → `value.label` "Diesel"
- Przebieg: `params[].key=="milage"` → `value.label` "181 346 km"
- Region: `location.region.name` (np. "warmińsko-mazurskie")
- Miasto: `location.city.name`

## Dowód 26: Region Mazowsze

Nie potwierdzony numerycznie jeszcze, ale mamy listę regionów z JSON (id=4 małopolskie, 6 śląskie, 7 łódzkie, 14 warmińsko-mazurskie, 17 podkarpackie). Mazowsze do ustalenia — ale dla bota można filtrować po `location.region.name == "mazowieckie"` (tekst), co jest prostsze.

---

## STATUS: fundament metody potwierdzony

1. ✅ API działa (`/api/v1/offers/`)
2. ✅ Odczyt po numerycznym ID działa
3. ✅ ID rośnie globalnie
4. ✅ Znamy category.id dla aut (203) i telefonów (2912)
5. ✅ Znamy filtr cross-list otomoto
6. ⚠️ Nie potwierdzone: czy nieistniejące ID zwracają 404 (test w prototypie)
7. ⚠️ Niewiadoma: czy Python/requests z lokalnego IP dostanie 403 (CloudFront) — do testu

## NASTĘPNY KROK: prototyp bota

Zbudować prototyp w Pythonie:
- Pobierz listę najnowszych ofert → max ID
- Skanuj ID w górę (co 1)
- Filtruj po category.id (203=auta, 2912=telefony)
- Odrzucaj cross-listy otomoto
- Loguj detekcje do pliku + konsola
- Test z lokalnego IP (czy requests przechodzi CloudFront)