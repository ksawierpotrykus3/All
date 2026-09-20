# AI Integracja – DeepSeek V4 Pro

> Jak używamy AI w projekcie: model, endpoint, dwa etapy działania.

---

## Model AI

**DeepSeek V4 Pro** – darmowy, działa lokalnie.

### Endpoint

```
http://localhost:4570/v1
```

API kompatybilne z formatem OpenAI (używamy biblioteki `openai` tylko jako klienta HTTP, łączymy się wyłącznie z localhost – nie z serwerami OpenAI).

---

## Lokalizacja gotowej paczki proxy DeepSeek (AI)

AI (DeepSeek) korzysta z gotowej paczki proxy — **nie** z „głównego" proxy do kodowania:

```
c:\Users\Ksawier\Pictures\Screenshots\deepseek-proxy-clean\proxy_pakiet
```

- **Start:** `start.bat` → menu (1 = normalny, 2 = czysty `--clean`)
- **Tryb czysty** używa własnego promptu z `prompt2.txt` (może być pusty). Główne proxy miało długi prompt „jak kodować" — tutaj AI robi co innego niż kodowanie, więc ten długi prompt jest zbędny.
- **Endpoint OpenAI-compatible:** `http://localhost:4570/v1` (modele: `deepseek-v4-pro`, `deepseek-vision`)
- **Rzeczywisty port** zapisywany w `data/port.txt` (gdy 4570 zajęty → wolny port)
- **Tryb:** `data/proxy_mode.txt` (aktualnie `free_first`)
- **Konta web-chat (max 3):** `login_slot.bat` (slot 0/1/2)
- **Klucz oficjalnego API (fallback):** `data/deepseek_api_key.txt`

---

## Dwa etapy AI

### AI #1 – Selekcja ofert

**Co dostaje:**
- Listę nowych ofert (krótkie opisy z listy – tytuł, budżet, kategoria, pierwsze ~200 znaków opisu)
- Plik(i) z wytycznymi (osobne, łatwe do edycji)
- Prompt (osobny plik, ustalony przez użytkownika)

**Co robi:**
- Analizuje każdą ofertę
- Decyduje, które pasują do umiejętności / preferencji
- Zwraca listę wybranych ofert (może być 0, może być wszystkie)

**Wynik:** lista tytułów/linków ofert do dalszego sprawdzenia.

---

### AI #2 – Generowanie treści propozycji

**Co dostaje:**
- Pełne dane JEDNEJ oferty (opis po kliknięciu "pokaż pełny opis", umiejętności, budżet, kategoria, prawa autorskie)
- Plik(i) z wytycznymi – jak pisać, styl, stawki
- Prompt (osobny plik, ustalony przez użytkownika)

**Co robi:**
- Generuje gotową treść propozycji do wysłania zleceniodawcy
- Proponuje stawkę (jeśli budżet "Do negocjacji")

**Wynik:** tekst propozycji + stawka.

**Wywołanie:** po kolei dla każdej oferty (nie równolegle). Np. 2 wybrane oferty = 2 wywołania AI #2, jedno po drugim.

---

## Prompt i pliki konfiguracyjne

**Prompt NIE jest ustalony na sztywno.** Będzie w osobnych plikach, łatwych do edycji:

| Plik | Dla kogo | Do czego |
|---|---|---|
| `prompt_ai1.md` | AI #1 | Jakie oferty wybierać |
| `prompt_ai2.md` | AI #2 | Jak pisać propozycje |
| `lore.md` / inne | Oba AI | Dodatkowy kontekst (umiejętności, portfolio, styl) |

Pliki mogą być `.txt` lub `.md` – cokolwiek jest wygodniejsze.
Użytkownik może je zmieniać w każdej chwili, bez dotykania kodu Python.

---

## Jak używać w Pythonie (szkic)

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:4570/v1",
    api_key="not-needed"
)

def call_ai1(offers_list, prompt_text, wytyczne_text):
    response = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[
            {"role": "system", "content": wytyczne_text},
            {"role": "user", "content": f"{prompt_text}\n\nOferty:\n{offers_list}"}
        ]
    )
    return response.choices[0].message.content

def call_ai2(offer_details, prompt_text, wytyczne_text):
    response = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[
            {"role": "system", "content": wytyczne_text},
            {"role": "user", "content": f"{prompt_text}\n\nOferta:\n{offer_details}"}
        ]
    )
    return response.choices[0].message.content
```

---

## Ograniczenia DeepSeek V4 Pro

- ❌ Brak obsługi wizji/obrazów – nie wysyłamy screenshotów
- ✅ Tylko tekst
- ❓ Darmowy, może mieć limity
- ❓ Trzeba mieć odpalony serwer lokalnie

---

## Sprawdzone w labie (testy 04-05, 2026-08-06)

### Endpoint działa ✅
- `http://localhost:4570/v1` → 200 OK
- Dostępne modele: `deepseek-v4-pro`, `deepseek-vision`
- Używamy wyłącznie `deepseek-v4-pro`

### AI #1 (selekcja) – działa ✅
- Trafnie wyselekcjonowała 1 z 10 ofert pasującą do profilu (Python + web scraping + automatyzacja)
- 9 odrzuconych z logicznymi uzasadnieniami (inny stack, brak Pythona)
- Odpowiedź w czystym JSON zgodnie z wymaganiami promptu

### AI #2 (generowanie propozycji) – działa ✅
- Generuje sensowne propozycje (3-8 zdań, konkretne biblioteki: BeautifulSoup, Scrapy, Playwright, Tesseract)
- Proponuje stawki (110 PLN/h, 95 PLN/h itd.)
- Czas odpowiedzi: kilka sekund

### Problemy techniczne (rozwiązane)
1. **Biblioteka `openai` (v2.53.0) zwracała surowy strumień SSE** mimo `stream=False` → rozwiązanie: bezpośrednio `requests.post()` z ręcznym parsowaniem chunków SSE
2. **Odpowiedź API zawierała znacznik `<!-- PROXY_SID:...-->` na końcu** → usuwany regexem przed parsowaniem JSON
3. **Pliki JSON z BOM** (`utf-8` z BOM) → czytać przez `utf-8-sig`
4. **Podwójnie escape'owane cudzysłowy** (`\"`) → `replace('\\"', '"')` przed parsowaniem

### Znany błąd AI (do poprawy w promptach)
- W teście 06 AI #2 **pomyliło kontekst** – dla oferty "Inteligentna Platforma AI" wygenerowało propozycję o "aplikacji desktopowej do PDF" (skojarzyło z inną ofertą). Przy wielu ofertach wysyłanych po kolei trzeba pilnować, żeby kontekst się nie mieszał – dać AI #2 wyraźnie TYLKO dane jednej oferty i dodać do promptu nazwę/tytuł oferty.

---

## Status

- [x] Potwierdzić dokładną nazwę modelu w API → `deepseek-v4-pro`
- [x] Sprawdzić, czy endpoint `http://localhost:4570/v1` działa → ✅
- [x] Przetestować połączenie Python → DeepSeek → ✅ (przez `requests`, nie przez `openai`)