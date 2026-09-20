# Logika iteracji – jak pobieramy oferty

> Mechanizm ściągania ofert po 10, marker, deduplikacja.

---

## Koncept

Skrypt za każdym uruchomieniem:
1. Wchodzi na link kategorii
2. Pobiera oferty z góry strony (najnowsze pierwsze)
3. Porównuje z magazynem (po ID z URL; zapasowo po autor + tytuł) – nowe = te, których jeszcze nie ma w magazynie
4. Zapisuje WSZYSTKIE pobrane oferty do magazynu (każda w osobnym pliku)
5. Aktualizuje marker (najnowszy rekord w magazynie)

---

## Po czym bot poznaje, że oferta już była

Bot porównuje każdą ofertę z listy z zawartością magazynu (folder z plikami).

**Główny klucz: numer oferty (ID).**
Numer NIE jest losowy – jest zapisany w linku każdej oferty na liście.
Przykład linku: `https://useme.com/pl/jobs/projekt-wnetrza,142303/` → ID = `142303`.
Bot czyta ten link już na poziomie listy, bez klikania w ofertę.

**Zapasowy klucz: autor + tytuł (razem).**
Gdyby linku nie dało się odczytać, bot porównuje parę:
- kto dodał (np. „Piotr Torchała”)
- i tytuł (np. „Projekt wnętrza dla domu 120mkw”)

Jeśli w magazynie jest już taka sama para → oferta jest stara, pomijamy ją.
Jeśli nie ma → oferta jest nowa i zapisujemy ją.

Dzięki temu bot NIE musi zgadywać. Używa numeru z linku, a jak go nie ma – używa autora + tytułu.

---

## Marker

Marker to **najnowszy rekord z magazynu** (największe ID oferty lub najświeższa data pojawienia się w magazynie).

Plik: `marker.json`

Służy tylko pomocniczo – do szybkiego podglądu i logów. **Decyzję o tym, czy oferta jest nowa, podejmuje magazyn** (czy URL już istnieje), a nie marker.

---

## Jak działa

### Tura 1 (pierwsze uruchomienie):

```
Pobrano: [A, B, C, D, E, F, G, H, I, J]  (oferty, najnowsza na górze)
Magazyn pusty → wszystkie są nowe
Zapisujemy wszystkie do magazynu (każda w osobnym pliku)
Marker = A (najnowsza z magazynu)
```

### Tura 2 (kolejne uruchomienie):

```
Pobrano: [K, L, M, N, O, A, B, C, D, E]  (nowe K–O, stare A–E)
Magazyn zawiera już A–J

Porównujemy każdą pobraną ofertę z magazynem po URL:
  K → brak w magazynie → NOWA ✓
  L → brak w magazynie → NOWA ✓
  M → brak w magazynie → NOWA ✓
  N → brak w magazynie → NOWA ✓
  O → brak w magazynie → NOWA ✓
  A → jest w magazynie → STARA (pomijamy)
  ...

Nowych: 5 (K, L, M, N, O)
Wszystkie pobrane (K–E) dopisujemy do magazynu (stare już tam są – nie duplikujemy)
Marker = K (najnowsza z magazynu)
```

### Tura 3 (tylko 1 nowa):

```
Pobrano: [X, K, L, M, N, O, A, B, C, D]
Magazyn zawiera K–J

Porównujemy po URL:
  X → brak w magazynie → NOWA ✓
  K → jest → STARA
  ...

Nowych: 1 (tylko X)
X dopisujemy do magazynu
Marker = X
```

### Tura 4 (brak nowych):

```
Pobrano: [X, K, L, M, N, O, A, B, C, D]  (takie same jak ostatnio)
Magazyn zawiera X, K–J

Porównujemy po URL:
  X → jest → STARA
  K → jest → STARA
  ...

Nowych: 0
Nic nowego nie dodajemy do magazynu, marker bez zmian.
```

---

## Co idzie do AI

Wszystkie nowe oferty – **nawet jeśli to tylko 1 sztuka.**
1 nowa → AI #1 dostaje 1 ofertę do analizy.
10 nowych → AI #1 dostaje 10 ofert do analizy.

---

## Magazyn ofert (wymaganie użytkownika, 2026-08-06)

**Wszystkie** oferty z 2 kategorii trafiają do magazynu. Magazyn to **folder**, a nie jeden wielki plik.
Każda oferta ma swój **osobny plik JSON**.

### Struktura magazynu

```
useme_core/
└── magazyn/
    ├── programowanie-i-it/
    │   ├── 142303.json   ← jedna oferta = jeden plik
    │   ├── 142302.json
    │   └── ...
    └── serwisy-internetowe/
        └── ...
```

- Nazwa pliku = ID oferty z URL (np. `142303` z `.../jobs/tresc,142303/`)
- Każdy plik zawiera: dane z listy + status + (później) detale i naszą ofertę
- **Stare oferty NIGDY nie są usuwane** – plików tylko przybywa
- Po wysłaniu oferty uzupełniamy TEN SAM plik (nie tworzymy drugiego)

### 1. Oferta, do której NIE wysłaliśmy oferty → zapis KRÓTKI

W pliku oferty zapisuje się (bez liczby ofert i bez "Znika za..." – to zbędne):

- ID (z URL)
- URL
- Autor (zleceniodawca)
- Tytuł
- Opis (krótki, z listy)
- Kategoria główna + szczegółowa
- Budżet
- Status: NOWA

### 2. Oferta, do której WYSŁALIŚMY ofertę → TEN SAM plik dostaje zapis PEŁNY

Do istniejącego pliku oferty dopisujemy:

- **Pełne zlecenie** (wszystkie dane, z detalu)
- **Nasza oferta** (wygenerowana propozycja AI #2)
- Status: WYSŁANO OFERTĘ

### Przekazywanie dalej

Nowe oferty (te, których nie ma jeszcze w magazynie) idą dalej w procesie:
nowe → AI #1 (selekcja) → detale → AI #2 (propozycja) → formularz.

## Statusy oferty (do badań)

Każda oferta w magazynie ma status:

```
NOWA (świeżo pobrana)
  │
  ▼
WYSŁANO OFERTĘ (wysłaliśmy propozycję)
  ├── ODPOWIEDZIELI (odpisali)
  └── NIE ODPOWIEDZIELI (brak odpowiedzi)
```

- „Odpowiedzieli / nie odpowiedzieli" odznaczamy **ręcznie** (np. po sprawdzeniu skrzynki) – na razie bez automatu

---

## Pliki

| Plik/Folder | Zawartość |
|---|---|
| `marker.json` | Najnowsza oferta z magazynu (ID lub data) – tylko do podglądu/logów |
| `magazyn/` | **MAGAZYN:** folder z podfolderami per kategoria. Każda oferta = osobny plik `<ID>.json` (tytuł, URL, autor, kategoria, budżet, termin, status; po wysyłce + pełne dane + nasza oferta) |
| `nowe_oferty.json` | Nowe oferty z ostatniej tury (brak w magazynie) → idą do AI #1 |

---

## Sprawdzone w labie (test 06, 2026-08-06)

- Marker w praktyce działa jako prosty plik tekstowy (`last_offer.txt`) – zapisuje ostatnią ofertę z tury
- Pierwsze uruchomienie: wszystkie 10 ofert oznaczone jako NOWE (brak wcześniejszego markera)
- Mechanizm "od nowej do markera" potwierdzony w działającym flow
- Pełny łańcuch działa: lista (10) → marker → AI #1 (5 wybranych) → szczegóły (5/5) → AI #2 (5/5 propozycji)
- Uwaga: AI #1 wybrało w teście 06 aż 5 ofert (prompt był luźniejszy) – selekcja zależy mocno od treści promptu, to jest do dopracowania