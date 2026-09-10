# CHECKSUM — CZY DA SIĘ ODTWORZYĆ DETERMINISTYCZNIE?

**Data:** 2026-08-31
**Metoda:** analiza APK (jadx) + web JS (chunks_har)
**Konwencja:** `[UDOWODNIONE]` (z kodu źródłowego)

---

## Werdykt: NIE — checksum jest generowany wyłącznie po stronie backendu

Sprawdzono wszystkie punkty z planu. Konkluzja jednoznaczna: **checksum nie jest liczony ani po stronie aplikacji (APK), ani po stronie web (JS)**. Klient tylko **deserializuje** go z odpowiedzi `checkout/build` i **odsyła z powrotem** przy `payment`/`payment/continue`.

---

## Punkt 1-2: porównanie checksum z buildów

Wyniki bota (`bot/output/wynik_*.json`) **nie zapisują surowego `checksum`** — bot tylko wyciąga go do payment, ale nie wrzuca do JSON wyjściowego. Nie ma więc istniejących danych do porównania deterministyczności bez wysyłania nowych requestów.

**Ale** to nie ma znaczenia — bo kod źródłowy rozstrzyga sprawę (patrz niżej).

---

## Punkt 4: web JS — checksum tylko deserializowany [UDOWODNIONE]

**Chunk `0m6z-r2_~i3np.js` (linia ~108181):**

```js
i1 = e => {
  let { id, checksum, adyen_protect_signals_enabled, components, navigation } = e;
  // ... dalej checksum używane jako _.checksum
  return { checksum: n, checkoutId: i, ... };
}
```

`checksum` jest polem **wejściowego obiektu `e`** (czyli odpowiedzi serwera), a nie wyniku żadnej funkcji haszującej. Klient go **czyta**, nie liczy.

**Chunk `0p3.vfb7uddnl.js` (endpointy):**

```js
"continueSingleCheckoutPayment": (e, t) =>
  i.api.post(`purchases/${e}/checkout/payment/continue`,
    e => { let { checksum: i, ... } = e; return { checksum: i, payment_options: {...} }; }
  )
```

Przy `payment` i `payment/continue` klient **wstawia checksum wprost do body** — przepuszcza go, nie generuje.

---

## Punkt 3: Frida — zbędna

Brak emulatora Android, ale **nie jest potrzebna**: skoro checksum nie jest liczony lokalnie (ani w APK, ani w JS), nie ma lokalnego algorytmu do zhookowania. Frida na deserialize `NewBackendCheckoutDtoSerializer` pokazałaby tylko to samo — wartość przychodzącą z serwera.

---

## Wnioski

1. **[UDOWODNIONE]** Checksum = podpis/suma kontrolna checkoutu generowana **serwerowo** (prawdopodobnie z `components` + sekret serwera).
2. **[UDOWODNIONE]** Zarówno APK, jak i web **nie liczą checksum lokalnie** — tylko przepuszczają wartość z backendu.
3. **[WNIOSEK]** Checksum jest **nieodtwarzalny deterministycznie** po stronie klienta. Trzeba go zdobywać **żywcem** (przez `checkout/build`).
4. **[WNIOSEK]** `purchase_id` + `checksum` są związane z konkretnym checkoutem i **nieprzenoszalne** na inne produkty.

## Co to oznacza operacyjnie

Jedyna droga bez buildu to `payment/continue` na **tym samym** `purchase_id` (retry po nieudanej płatności). Nowy produkt = nowy build = nowy checksum. Nie da się tego obejść bez kompromisu z backendem.

---

## Źródła

- `NewBackendCheckoutDtoSerializer.java` — deserialize checksum z JSON
- `NewBackendCheckoutDto.java` — checksum jako pole dto
- `chunks_har/0m6z-r2_~i3np.js` — web deserializacja checksum
- `chunks_har/0p3.vfb7uddnl.js` — web endpointy payment (checksum w body)

---

*Koniec analizy.*