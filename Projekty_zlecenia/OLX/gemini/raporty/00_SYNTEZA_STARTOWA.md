# Raport 00: Stan Wiedzy Startowej i Obalone Mity

> Data: 2026-09-02
> Autor: Antigravity (Gemini)

## 1. Co jest twardo udowodnione [UDOWODNIONE]

1. **Detekcja ofert działa z przewagą 9-14 minut nad wyszukiwarką**
   - Mechanizm sekwencyjnego przewidywania ID ofert + sliding window + hole-sweeper (`bot/detector.py`).
   - Udowodnione w logach audytów i testach porównawczych.

2. **Obejście blokad CloudFront 403**
   - Połączenia przez `curl_cffi` z parametrem `impersonate="chrome124"` omijają TLS fingerprinting CloudFronta.

3. **Autoryzacja Bearer tokenem na API OLX**
   - `GET https://www.olx.pl/api/v1/users/me/` z nagłówkiem `Authorization: Bearer {access_token}` zwraca kod `200` i profil użytkownika (id 2553769477).
   - Obalono tezę, że OLX nie udostępnia API dla zalogowanych użytkowników.

4. **Krótki czas życia tokena: TTL = 15 minut (900 sekund)**
   - Wartości z nagłówka JWT: `exp - iat = 900 s`.
   - Po 15 minutach API natychmiast zwraca: `401 Unauthorized` (`{"error":"invalid_token","error_description":"Invalid JWT token: Expired token"}`).

5. **Struktura delivery.rock**
   - Prawdziwym wskaźnikiem dostępności przesyłki jest pole `delivery.rock`.
   - Wartości trybu `mode`: `BuyWithDelivery`, `NotEligible`, `Ask4Delivery`.

---

## 2. Co zostało bezsprzecznie obalone [OBALONE]

1. **[OBALONE] Teoria o endpointach z koncepcji 08**
   - Endpointy `POST /delivery/checkout/{id}/`, `/api/v1/delivery/orders/`, `/api/v1/delivery/buyers/profile/` zwracają `404 Not Found`.

2. **[OBALONE] Teoria, że refresh token leży w `localStorage`**
   - Zrzut `localStorage` z przeglądarki zalogowanego użytkownika wykazał brak jakichkolwiek kluczy autoryzacyjnych Cognito/OAuth. Klucz `f_token` był pusty.

3. **[OBALONE] Teoria, że refresh token leży w `sessionStorage` lub `IndexedDB`**
   - `sessionStorage` zawiera wyłącznie telemetryczne klucze ankiet Maze (`maze-us`, `maze:widgets`) oraz rozszerzenia wideo (`savefrom-helper-extension`).
   - W magazynach przeglądarki nie ma wyodrębnionego klucza refresh token.

4. **[OBALONE] Metoda manualnego kopiowania ciasteczek do plików tekstowych**
   - Przy TTL = 15 minut ręczne kopiowanie ciasteczek powoduje, że token wygasa zanim skrypt zdąży wykonać sekwencję checkoutu.

---

## 3. Prawdziwa architektura sesji OLX [POTWIERDZONE]

* OLX bazuje na serwerze autoryzacyjnym AWS Cognito pod domeną **`login.olx.pl`** (Client ID: `6j7elk01p32o648o1io8lvhhab`).
* Strona `www.olx.pl` korzysta z mechanizmu cichej reautoryzacji (`silent authentication`):
  `GET https://login.olx.pl/oauth2/authorize?client_id=...&prompt=none&response_mode=web_message`
* Cicha reautoryzacja wymaga ciasteczek sesyjnych serwera `login.olx.pl`, które są ustawiane wyłącznie podczas interaktywnego logowania w przeglądarce.
* Jeśli tych ciasteczek brakuje, serwer odpowiada:
  `{"error":"login_required","error_description":"User is not logged in, silent authentication is not possible"}`
  i aplikacja przekierowuje użytkownika do pełnego formularza logowania.

---

## 4. Wnioski architektoniczne dla bota OLX

Identycznie jak w sprawdzonym projekcie **Vinted**, jedynym stabilnym, odpornym na wygasanie rozwiązaniem jest **trwały profil przeglądarki (`persistent_context`)**.
Użytkownik loguje się raz w oknie przeglądarki, a profil zachowuje stan sesji na stałe na dysku.
