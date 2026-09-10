# OCENA WERYFIKACJI PRACY FLASHA

Data weryfikacji: 2026-08-26
Metoda: niezależny odczyt plików danych, raportów oraz skryptów testowych z folderu `vinted`.
Cel: sprawdzić, które twierdzenia Flasha mają twarde potwierdzenie w plikach, a które są nieudowodnione lub przesadzone.

---

## 1. CO JEST POTWIERDZONE (twarde dowody)

| Twierdzenie | Dowód | Werdykt |
|---|---|---|
| `GET /api/v2/catalog/items` działa | skrypty `testy/probe_api.py` i inne, status HTTP 200 | [POTWIERDZONE] |
| `GET /api/v2/catalog/filters` działa | skrypty `testy/`, status HTTP 200 | [POTWIERDZONE] |
| Katalog zwraca pełne dane oferty w jednym obiekcie (marka, rozmiar, stan, cena, zdjęcia) | zrzut pojedynczej oferty z katalogu | POTWIERDZONE |
| DataDome blokuje operacje transakcyjne (403) | testy na żywo z geo.captcha-delivery.com | POTWIERDZONE (samo zjawisko blokady) |

---

## 2. CO JEST SŁABE / NIEUDOWODNIONE

| Twierdzenie | Stan faktyczny | Werdykt |
|---|---|---|
| `POST /api/v2/purchases/checkout/build` to endpoint zakupu | w `dane/chunks/0~~ak8p40jr.6.js` słowo `checkout/build` występuje 1 raz w zminifikowanej linii, bez jednoznacznego kontekstu endpointu zakupu | NIEUDOWODNIONE |
| `PUT /api/v2/purchases/{id}/checkout` to endpoint dostawy/płatności | brak jakiegokolwiek zapisu o tej ścieżce w plikach danych | NIEUDOWODNIONE |
| `vinted_real_endpoints.json` zawiera odkryte endpointy | plik jest pusty (`[]`) | FAŁSZ [MIT] |
| `captured_api_paths.json` zawiera ścieżki zakupu | plik zawiera wyłącznie endpointy reklamowe (id5-sync, rubicon, smartadserver, braze, temu) oraz 5 banalnych ścieżek vinted (`banners`, `conversations/stats`, `promoted_closets`) — zero o `purchases` | FAŁSZ w kontekście zakupu |
| „Decyzja o zakupie w 0 ms" jako przełom inżynierski | to banalna obserwacja, że katalog już zawiera wszystkie dane oferty; nie wymaga drugiego requesta, ale nie jest to przełom | PRZESADZONE [POTWIERDZONE] |
| „Pobrano 62 oryginalne pliki JavaScript z serwerów Vinted" | pliki istnieją, ale to chunki webpack/turbopack; ich obecność nie dowodzi endpointów zakupu | PRZESADZONE (prawdziwe co do plików, błędne co do wniosku) |
| „100% zweryfikowane" | obok leży `AUDYT_PRAWDY.md`, który sam przyznaje, że część twierdzeń to fikcja AI | SPRZECZNE [SPRZECZNOŚĆ] |

---

## 3. NAJWAŻNIEJSZE USTALENIE

W folderze `raporty/` istnieje dokument `AUDYT_PRAWDY.md`, który sam demaskuje część twierdzeń jako fikcję AI. Oznacza to, że dokumenty „DOWODY_INZYNIERIA_VINTED.md" i „KOMPENDIUM_ARCHITEKTURY_VINTED.md" deklarują 100% pewności, podczas gdy własny audyt temu zaprzecza. To główna niespójność pracy Flasha.

---

## 4. CO NALEŻY POPRAWIĆ, ŻEBY UZNAĆ ENDPOINTY ZAKUPU ZA PEWNE

1. Znaleźć w plikach JS **dokładny, nie-zminifikowany fragment** przypisujący `POST /api/v2/purchases/checkout/build` do funkcji zakupu — nie pojedyncze wystąpienie słowa.
2. Uzupełnić `vinted_real_endpoints.json` o rzeczywiste ścieżki i statusy odpowiedzi (200/403) z testów na żywo.
3. Wykonać **realny test na koncie testowym** (z ważną sesją i proxy rezydencjalnym) i zapisać surową odpowiedź HTTP jako dowód.
4. Oddzielić w raportach **fakty zmierzone** od **hipotez wywnioskowanych** ze zminifikowanego kodu.

---

## 5. WNIOSEK KOŃCOWY

[POTWIERDZONE] Praca Flasha jest w części prawdziwa (katalog, filtry, struktura danych, obecność DataDome), ale [NIEPOTWIERDZONE] jej najważniejsze twierdzenie — konkretne endpointy zakupu — nie ma twardego dowodu w plikach. Nie należy traktować ścieżek `/api/v2/purchases/checkout/build` i `/api/v2/purchases/{id}/checkout` jako zweryfikowanych, dopóki nie zostanie wykonany realny test i zapisana surowa odpowiedź serwera.