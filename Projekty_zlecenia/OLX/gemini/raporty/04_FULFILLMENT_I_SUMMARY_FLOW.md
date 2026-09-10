# Raport 04: Przejście Kroku Paczkomatu, Przechwycenie Payloadów i Stan Blokady

> Data: 2026-09-02T19:45:00+02:00
> Status: [UDOWODNIONE dla payloadów API] / [HIPOTEZA dla momentu blokady]
> Skrypt testowy: `gemini/skrypty/test_select_paczkomat_and_lock.py`
> Dowód surowy: `gemini/dane/paczkomat_and_lock_proof.json`
> Zrzut podsumowania: `gemini/dane/checkout_step4_final.png`

---

## 1. Rozwiązanie problemu wyboru Paczkomatu

Poprzednie testy (w tym próby DeepSeeka) utknęły na mapie, ponieważ używały zgadywanych selektorów (`[data-testid*='locker']`, `pickup-point`).
Zbadaliśmy surowy DOM modalu i zidentyfikowaliśmy prawdziwy selektor przycisków punktów odbioru:
```css
button[data-testid='map-list-item']
```
Kliknięcie punktu z tym selektorem natychmiast przypisuje wybrany Paczkomat (np. `inpost:PAR01BAPP`) i odblokowuje przycisk „Dalej”.

---

## 2. Przechwycone endpointy i payloady kroków formularza [UDOWODNIONE]

Po kliknięciu „Dalej” na formularzu dostawy strona wysyła serię czystych zapytań POST z kodem odpowiedzi `202 Accepted`:

### A. Wybór Paczkomatu:
```http
POST https://pl.ps.prd.eu.olx.org/fulfillment/v1/fulfillment/{fulfillment_id}/pick-up-point/submit
Content-Type: application/json

{
  "servicePointId": "inpost:PAR01BAPP"
}
```

### B. Dane odbiorcy:
```http
POST https://pl.ps.prd.eu.olx.org/fulfillment/v1/fulfillment/{fulfillment_id}/personal-details/submit
Content-Type: application/json

{
  "firstName": "Ksaw",
  "lastName": "Ksaw",
  "email": "ksawierpotrykus3@gmail.com",
  "phoneNumber": "+48515151600"
}
```

### C. Metoda płatności:
```http
POST https://pl.ps.prd.eu.olx.org/order/v1/purchase-order/{order_id}/payment-method-selection/submit
Content-Type: application/json

{
  "paymentMethod": "BANK_TRANSFER"
}
```

### D. Darowizna:
```http
POST https://pl.ps.prd.eu.olx.org/order/v1/purchase-order/{order_id}/donation-selection/submit
Content-Type: application/json

{
  "selection": {
    "id": "SUPPORT_UKRAINE",
    "value": {
      "amount": 0,
      "currency": "PLN"
    }
  }
}
```

### E. Faktura:
```http
POST https://pl.ps.prd.eu.olx.org/invoicing/v1/billing/{billing_id}/billing-needed/submit
Content-Type: application/json

{
  "needed": false
}
```

Wszystkie te zapytania są w 100% powtarzalnymi, lekkimi zapytaniami REST API, które bot może wykonać sekwencyjnie w ułamku sekundy.

---

## 3. Ekran Podsumowania (`#summary`) i Stan Blokady

Po wykonaniu powyższych zapytań checkout przechodzi pod adres:
`https://www.olx.pl/delivery/checkout/{purchase_order_id}/#summary`
(zrzut ekranu: `gemini/dane/checkout_step4_final.png`).

Na ekranie widoczne są:
- Wybrany Paczkomat InPost,
- Dane odbiorcy,
- Metoda płatności online,
- Checkbox regulaminu,
- Przycisk **„Zamawiam i płacę”**.

### Wynik weryfikacji blokady w publicznym API:
Wysłano zapytanie do publicznego API `GET https://www.olx.pl/api/v1/offers/1018987579/`:
```json
{
  "status": "active",
  "delivery": {
    "rock": {
      "active": true,
      "mode": "BuyWithDelivery"
    }
  }
}
```

### Twardy podział: Co jest faktem, a co hipotezą

1. **[UDOWODNIONE]**: Nawet po wypełnieniu Paczkomatu, danych odbiorcy i wejściu na `#summary` **oferta NIE jest zablokowana** (`delivery.rock.active` nadal wynosi `True`).
2. **[HIPOTEZA]**: Zablokowanie oferty (mechanizm 15-minutowej rezerwacji przed innymi) zapada dopiero po wysłaniu zatwierdzenia zakupu:
   `POST .../purchase-order/{order_id}/buyer-confirmation/submit` (przycisk „Zamawiam i płacę”).
   *Uwaga: Ten krok nie został wykonany, ponieważ wiąże się z realnym obciążeniem finansowym (62,48 zł) i wygenerowaniem właściwego zamówienia.*
