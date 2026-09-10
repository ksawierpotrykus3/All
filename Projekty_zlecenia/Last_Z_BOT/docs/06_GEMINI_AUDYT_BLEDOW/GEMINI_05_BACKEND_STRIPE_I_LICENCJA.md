# GEMINI AUDYT CZĘŚĆ 5: BACKEND, PŁATNOŚCI STRIPE I SYSTEM LICENCJI
**Pliki audytowane:** `mvp/backend/main.py`, `mvp/backend/database.py`, `mvp/backend/models.py`, `mvp/license.py`, `PORADNIK_KLIENT.md`

---

## 1. BŁĄD KRYTYCZNY: Webhook Stripe gubi użytkownika i nie aktywuje licencji

### Dowód w kodzie
Plik: `mvp/backend/main.py:213, 336-360`

Przy tworzeniu sesji płatności (`create_checkout_session`, linia 213):
```python
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": settings.stripe_price_id, "quantity": 1}],
        customer_email=user.email,
        success_url=str(data.success_url),
        cancel_url=str(data.cancel_url),
        metadata={"user_id": user.id}, # <--- user_id zapisany w metadanych Stripe
    )
```

W obsłudze webhooka (`stripe_webhook`, linie 336–342):
```python
    if event_type == "checkout.session.completed":
        customer_email = data.get("customer_email") or data.get("customer_details", {}).get("email")
        stripe_customer_id = data.get("customer")
        if customer_email and stripe_customer_id:
            user = db.query(User).filter(User.email == customer_email).first()
            if user:
                ... # Aktywacja licencji
```

### Mechanizm awarii
1. Podczas płatności w bramce Stripe klient może zapłacić przez Apple Pay, Google Pay, kartę służbową lub wpisać inny adres e-mail (np. `jan.prywatny@gmail.com` zamiast `jan@firma.pl` użytego przy rejestracji konta).
2. Webhook Stripe sprawdza **wyłącznie pole adresu e-mail** (`User.email == customer_email`), całkowicie **ignorując pole `metadata.user_id`**!
3. Skutek:
   - Klient zostaje obciążony opłatą subskrypcyjną w Stripe.
   - Webhook zwraca HTTP 200 `{"status": "ok"}`, ale w bazie danych zapytanie zwraca `user = None`.
   - Obiekt `StripeCustomer` nie zostaje powiązany z kontem, a licencja klienta **pozostaje nieaktywna (`is_active = False`)**. Klient płaci, ale nie otrzymuje dostępu do produktu.

---

## 2. BŁĄD KRYTYCZNY: Blokada uruchomienia w wersji PROD (Puste wartości domyślne)

### Dowód w kodzie
Plik: `config.json:37-38`
```json
  "backend_url": "",
  "license_key": ""
```

Plik: `mvp/gui/main_window.py:700-705` oraz `mvp/license.py:80-83`:
```python
def validate_license(backend_url: str, license_key: str, hwid: str, ...) -> dict:
    if not backend_url or not license_key:
        raise LicenseError("Missing backend_url or license_key in config.json")
```

### Mechanizm awarii
- W skompilowanej wersji produkcyjnej (`LastZBot.exe` z `BUILD_MODE="prod"`), bot przy każdym naciśnięciu `START` lub klawisza `F6` sprawdza obecność licencji.
- Ponieważ `config.json` dostarczony w instalatorze ma puste wartości `backend_url` i `license_key`, `validate_license()` natychmiast wyrzuca wyjątek `LicenseError`.
- Użytkownik końcowy widzi, że program „w ogóle nie reaguje na przycisk F6”.

---

## 3. BŁĄD POWAŻNY: Blokowanie bazy SQLite przy asynchronicznym API FastAPI

### Dowód w kodzie
Plik: `mvp/backend/database.py:10-18` i `mvp/backend/main.py:240, 320`

- Domyślna konfiguracja bazy danych: `sqlite:///./joaxx.db`.
- API FastAPI działa w trybie asynchronicznym (`async def validate_license`, `async def stripe_webhook`).
- Sesje bazy danych (`SessionLocal`) są synchronicznymi połączeniami SQLAlchemy z pojedynczym plikiem SQLite na dysku.
- Przy równoczesnych zapytaniach od kilku klientów walidujących licencję (co minutę) lub nadejściu serii webhooków Stripe, SQLite blokuje transakcje, rzucając:
  `sqlite3.OperationalError: database is locked`
  i zwracając błędy HTTP 500.

---

## 4. BŁĄD ARCHITEKTONICZNY: Brak platformy sprzedażowej SaaS (Frontend / Panel)

### Dowód z dokumentacji projektu
Plik: `PORADNIK_KLIENT.md:6-9, 129-136`

> *„W tym projekcie backend licencyjny to tylko «silnik» (API) — bez strony, którą widzi klient. Twój klient nie kupi jeszcze sam przez internet. Na początku klucze wydaje się ręcznie.”*  
> *„Brak strony/sklepu dla klienta końcowego. Jest tylko API. Żeby klient «kupił i od razu dostał klucz» przez internet, trzeba dorobić prosty panel (frontend)... Brak panelu administracyjnego.”*

### Rozbieżność z umową zlecenia
Klient zamówił produkt w modelu: *„Minimum do startu sprzedaży subskrypcyjnej, obejmujący bota, panel lokalny oraz backend licencyjny z kontami użytkowników, logowaniem, integracją Stripe i weryfikacją aktywności licencji”*.
Dostarczenie samego API FastAPI w Dockerze bez gotowej strony zakupu uniemożliwia klientowi start sprzedaży i jest bezpośrednią przyczyną formalnego sporu na Useme.
