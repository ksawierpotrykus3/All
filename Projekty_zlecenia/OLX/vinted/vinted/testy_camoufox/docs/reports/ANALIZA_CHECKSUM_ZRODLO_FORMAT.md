# CHECKSUM — ŹRÓDŁO I FORMAT

**Data:** 2026-08-31
**Metoda:** analiza APK (jadx) + surowe response bota + HAR

---

## Werdykt kluczowy

**Checksum NIE przychodzi z `checkout/build`** — build zwraca tylko `{ id, components }`.

**Checksum przychodzi z `GET purchases/{id}/checkout`** — darmowy endpoint odczytu (bez buildu, bez Incognii).

---

## Wynik A: build nie zawiera checksum [UDOWODNIONE]

Surowa odpowiedź buildu (`build_body_1788177293.json`):
```json
{"checkout":{"id":"srJQA6tHL1mDH3ap_FBTx","components":{...}}}
```

`"checksum" in body` → **False**. Build daje `id` (purchase_id) i `components`, ale **nie** checksum.

## Wynik B: GET checkout zwraca checksum [UDOWODNIONE]

Z APK:
```java
// CheckoutApi.java
@GET("purchases/{id}/checkout")
Single<SingleCheckoutResponse> getSingleCheckoutData(@Path("id") String id);
```

`SingleCheckoutResponse` → `NewBackendCheckoutDto { id, checksum, components }`.

Czyli **`GET /api/v2/purchases/{checkout_id}/checkout`** zwraca checksum. To jest darmowe źródło — bez buildu, bez Incognii, samo odczytanie stanu checkoutu.

---

## Format checksum [UDOWODNIONE — live]

Z HAR (`www.vinted.pl_checkout.har`), realne requesty payment:

```
checksum = "<32hex>|<32hex>"
```

Przykłady:
```
e889afc66ab3230f5b0201c737efd93d|7ba723b4299658ab155fcf51d9ce17e6
e889afc66ab3230f5b0201c737efd93d|414c48dddde8a8413a65967ece0d1fff
8949f54c9c0e7fea166724f321926a57|2e143d215bea6ebfea331048cc21ef4f
```

**Obserwacja kluczowa [DOMNIEMANE]:**
- **Pierwsza część jest stała** dla tego samego checkoutu (`e889afc6...` powtarza się wielokrotnie).
- **Druga część zmienia się** po modyfikacji checkoutu (PUT components).

Struktura sugeruje: `checksum = md5(id/stała-część) | md5(components/zmienna-część)`. Dokładny algorytm nadal nieznany (generowany serwerowo), ale format i źródło są już jasne.

---

## Wnioski operacyjne

1. **[UDOWODNIONE]** Checksum zdobywa się **darmowym `GET purchases/{id}/checkout`**, nie trzeba buildu ani Incognii.
2. **[UDOWODNIONE]** Warunkiem jest posiadanie `checkout_id` (= purchase_id) — ten nadal bierze się z buildu lub `conversations` (skip-build).
3. **[DOMNIEMANE]** Checksum jest generowany serwerowo (nieodtwarzalny lokalnie), ale **odczytywalny** przez GET — nie jest "black box" do zgadnięcia.

---

## Źródła

- `build_body_1788177293.json` — surowa odpowiedź buildu (brak checksum)
- `CheckoutApi.java` — `getSingleCheckoutData` (GET checkout)
- `SingleCheckoutResponse.java` → `NewBackendCheckoutDto` (id, checksum, components)
- `www.vinted.pl_checkout.har` — realne checksum w body payment

---

*Koniec analizy.*