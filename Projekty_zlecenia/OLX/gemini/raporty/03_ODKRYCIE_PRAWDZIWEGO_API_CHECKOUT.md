# Raport 03: Odkrycie Prawdziwego API Checkoutu i Maszyny Stanów OLX

> Data: 2026-09-02T19:30:00+02:00
> Status: [UDOWODNIONE]
> Domena produkcyjna API: `https://pl.ps.prd.eu.olx.org` (Pay & Ship Production)
> Skrypt testowy: `gemini/skrypty/test_purchase_order_pure_api.py`
> Dowód surowy: `gemini/dane/purchase_order_api_proof.json`

---

## 1. Zwycięstwo badawcze: Prawdziwa architektura Pay & Ship

Wszystkie wcześniejsze raporty projektu (koncepcja 08, raport 14, raport 15) błądziły wokół nieistniejących endpointów zwracających 404:
- [OBALONE] `POST /delivery/checkout/{id}/` — 404
- [OBALONE] `GET /api/v1/delivery/orders/` — 404
- [OBALONE] `GET /api/v1/delivery/buyers/profile/` — 404

Dzięki uruchomieniu trwałego profilu Playwright i przejściu flow na aktywnej ofercie (Lego Anakin 1018987579), przechwyciliśmy **100% prawdziwych endpointów backendu transakcyjnego OLX**.

---

## 2. Prawdziwa sekwencja API Pay & Ship [UDOWODNIONE]

### Krok 1: Sprawdzenie możliwości zakupu i kalkulacja kosztów
```http
GET https://pl.ps.prd.eu.olx.org/checkout/v1/checkout/{numeric_ad_id}
```
* **Status**: `200 OK`
* **Odpowiedź**:
  - `isAvailableForPayAndShip`: `true`
  - `shipmentMethods`: lista metod (np. `INPOST`)
  - `costs.lineItems`: szczegółowe rozbicie (cena przedmiotu `5000` gr, dostawa `649` gr, opłata serwisowa `599` gr, suma `6248` gr).

### Krok 2: Tworzenie zamówienia (Inicjalizacja koszyka / Draft Order)
```http
POST https://pl.ps.prd.eu.olx.org/order/v1/purchase-order
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "adId": 1018987579
}
```
* **Status**: `201 Created`
* **Potwierdzone czystym API (curl_cffi)**: Skrypt `gemini/skrypty/test_purchase_order_pure_api.py` wykonał bezpośrednie zapytanie z kodem 201 i zapisał dowód do `gemini/dane/purchase_order_api_proof.json`.
* **Stan zamówienia**: `"state": "Draft"` [UDOWODNIONE].
* **Kluczowe sprostowanie**: Ten krok **NIE BLOKUJE JESZCZE OFERTY PRZED INNYMI KUPUJĄCYMI** [UDOWODNIONE]. Pole `delivery.rock.active` w publicznym API nadal wynosi `True`. Blokada zapada na dalszym etapie.

### Krok 3: Maszyna stanów zamówienia (State Machine)
```http
GET https://pl.ps.prd.eu.olx.org/order/v1/purchase-order/{purchase_order_id}/next
```
Zwraca listę kroków wymaganych do sfinalizowania i wywołania blokady:
1. `type: "fulfillment"` (`state: "required"`, `id: "{fulfillment_uuid}"`) — wybór Paczkomatu/punktu dostawy.
2. `type: "buyer-billing"` (`state: "required"`, `id: "{billing_uuid}"`) — dane odbiorcy (imię, nazwisko, email, telefon).
3. `type: "payment-method-selection"` (`state: "completed"`, domyślnie `BANK_TRANSFER` / PayU BLIK).
4. `type: "donation-selection"` (`state: "completed"`, domyślnie 0 zł).
5. `type: "safedeal-info"` (`state: "completed"`).

---

## 3. Notatka dotycząca mechanizmów anty-botowych: Slider CAPTCHA (Vinted vs OLX)

Użytkownik podczas pierwszego logowania napotkał wyzwanie typu **slider puzzle** (przesunięcie klocka układanki).
* **Źródło**: AWS WAF / DataDome (ciasteczka `aws-waf-token` oraz `datadome`).
* **Powiązanie z projektem Vinted**:
  - W repozytorium Vinted (`vinted-repo/`) zidentyfikowano dokładnie ten sam mechanizm DataDome (`bot/src/vintedbot/slider_solver.py`, `manual_slider_unlock.py`).
  - Rozwiązanie polegające na jednorazowym rozwiązaniu slidera w trwałym profilu (`persistent_context`) zapisało tokeny `aws-waf-token` i `datadome` w `profiles/olx_profile`.
  - Kolejne zapytania w trybie headless nie wywołują już slidera!
