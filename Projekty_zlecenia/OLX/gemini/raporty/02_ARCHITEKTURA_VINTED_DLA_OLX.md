# Raport 02: Wdrożenie Architektury Trwałego Profilu (Wzorzec Vinted dla OLX)

> Data: 2026-09-02
> Status: [WDROŻONE]

## 1. Problem architektoniczny OLX
1. Token `access_token` jest krótkotrwałym tokenem JWT o czasie życia **zaledwie 15 minut** (`exp - iat = 900 s`).
2. Po upływie 15 minut każde zapytanie z tym tokenem zwraca `401 Unauthorized` [UDOWODNIONE w Raporcie 01].
3. Ręczne przekazywanie ciasteczek do plików tekstowych powoduje, że bot staje się bezużyteczny po kwadransie.
4. Token jest automatycznie odświeżany wyłącznie wewnątrz przeglądarki przez zapytanie cichej autoryzacji do serwera `login.olx.pl` (`prompt=none`), co wymaga obecności ciasteczek sesyjnych Cognito.

---

## 2. Rozwiązanie przeniesione z projektu Vinted

W projekcie Vinted (`vinted-repo/`) ten sam problem rozwiązano za pomocą mechanizmu **Persistent Context** (`user_data_dir`).

### Jak to działa w `gemini/`:
1. **Dedykowany katalog profilu**: `profiles/olx_profile`
   - Przeglądarka Chromium tworzy na dysku fizyczny profil, w którym trzyma:
     - Wszystkie ciasteczka (w tym `login.olx.pl`, `.olx.pl`, `www.olx.pl`).
     - Sesje logowania Google / Cognito.
     - Magazyny `localStorage` i `IndexedDB`.
2. **Jednorazowe logowanie**:
   - Uruchomienie skryptu `ZALOGUJ_SIE_OLX.bat` (lub `python gemini/skrypty/login_headed.py`).
   - Użytkownik loguje się raz w widocznym oknie.
   - Skrypt natychmiast po wykryciu tokena zapisuje stan sesji, synchronizuje `dane/cookies.txt` i weryfikuje profil testem HTTP `GET /api/v1/users/me/` (kod 200).
3. **Headless Auto-Refresh**:
   - Przed każdą operacją checkoutu lub testem bot uruchamia `gemini/skrypty/test_session_refresh.py`.
   - Przeglądarka w tle w ułamku sekundy pobiera najświeższy token od `login.olx.pl`, gwarantując, że token nigdy nie wygaśnie w trakcie transakcji.

---

## 3. Utworzone narzędzia

| Plik | Rola |
|---|---|
| `ZALOGUJ_SIE_OLX.bat` | Skrót dla użytkownika na pulpicie/głównym folderze do jednorazowego logowania |
| `gemini/skrypty/login_headed.py` | Silnik Playwright z persistent context i detektorem tokena |
| `gemini/skrypty/test_session_refresh.py` | Automatyczny headless refresh tokena + test API `/users/me/` |
| `gemini/skrypty/probe_checkout.py` | Interceptor zapytań checkoutu do przechwytywania prawdziwych endpointów zakupu |
