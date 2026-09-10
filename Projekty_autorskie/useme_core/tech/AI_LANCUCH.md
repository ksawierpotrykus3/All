# AI Łańcuch – system slotów (plug-and-play)

> Architektura pozwalająca dodawać/usuwać agentów AI w łańcuchu bez grzebania w kodzie.
> Jeden łańcuch = jedno zlecenie. 5 zleceń = 5 łańcuchów (każdy może mieć do 20 agentów).

---

## Koncepcja

Każdy agent AI to osobny "slot" – numerowane od `01` do `20`. Sloty są niezależne. Łańcuch odpala je sekwencyjnie, output jednego wchodzi do następnego + oryginalne dane zlecenia.

**Każdy agent zawsze widzi:**
- Oryginalne dane zlecenia (zawsze dostępne)
- Outputy wszystkich poprzednich slotów (po kluczach)
- Swój własny prompt (opcjonalnie – z pliku `.md`)
- Dodatkowe pliki kontekstowe (opcjonalnie – lista plików `.md`/`.txt`)

**Agent może działać bez własnych plików** – wystarczy mu to co dostał od poprzedników + dane zlecenia. Nie każdy musi mieć `prompt_file`.

**Włączanie/wyłączanie:** każdy slot ma w konfiguracji flagę `enabled: true/false`. Wyłączone sloty są pomijane.

**Dodawanie nowego agenta:** dodajesz wpis w `chain_config.json`. Jeśli potrzebuje prompta – tworzysz plik `.md` i podajesz ścieżkę. Jeśli nie – pomijasz `prompt_file`. Gotowe. Zero grzebania w Pythonie.

---

## Struktura plików

```
prompts/
├── prompt_ai1.md              # AI #1 – selekcja ofert (Krok 3)
├── agent_02a_opis_oferty.md   # AI #2a – treść oferty
├── agent_02b_wycena_dni.md    # AI #2b – wycena + dni pracy
├── agent_03_walidator_opisu.md  # Slot 03 – walidator (opcjonalny)
├── agent_04_spojnosc.md         # Slot 04 – sprawdza spójność (opcjonalny)
├── ...
├── agent_20_ostatni.md          # Slot 20 – ostatni w łańcuchu (opcjonalny)
└── lore.md                    # Wspólny kontekst (umiejętności, portfolio)

chain_config.json              # Konfiguracja slotów
```

---

## chain_config.json – format

```json
{
  "retry_max": 3,
  "slots": [
    {
      "id": "02b",
      "name": "Wycena i dni",
      "prompt_file": "agent_02b_wycena_dni.md",
      "context_files": ["lore.md", "mechanika_wyceniania.md"],
      "enabled": true,
      "role": "generator",
      "output_key": "wycena_dni"
    },
    {
      "id": "02a",
      "name": "Opis oferty",
      "prompt_file": "agent_02a_opis_oferty.md",
      "context_files": ["lore.md", "jak_pisac_oferty.md"],
      "enabled": true,
      "role": "generator",
      "output_key": "opis",
      "requires": ["wycena_dni"]
    },
    {
      "id": "03",
      "name": "Walidator opisu",
      "prompt_file": "agent_03_walidator_opisu.md",
      "context_files": ["lore.md", "zasady_wyceny.md"],
      "enabled": false,
      "role": "validator",
      "requires": ["opis"],
      "on_fail": "retry_from_02a"
    },
    {
      "id": "04",
      "name": "Spójność oferty",
      "enabled": false,
      "role": "validator",
      "requires": ["opis", "wycena_dni"],
      "on_fail": "abort"
    }
  ]
}
```

**Pola:**
- `id` – identyfikator slotu (string, np. "02a", "03")
- `name` – ludzka nazwa (do logów)
- `prompt_file` – (opcjonalny) ścieżka do pliku `.md` z promptem. Jeśli brak – agent działa tylko na danych z kontekstu
- `context_files` – (opcjonalny) lista dodatkowych plików `.md`/`.txt` dołączanych jako wiedza
- `enabled` – `true` = aktywny, `false` = pomijany
- `role` – `generator` (tworzy treść) lub `validator` (sprawdza i daje PASS/FAIL)
- `output_key` – klucz pod którym output trafia do kontekstu (dla generatorów)
- `requires` – lista kluczy outputów potrzebnych do działania (dla walidatorów)
- `on_fail` – co robić gdy validator da FAIL:
  - `retry_from_02a` – wróć do AI #2a i popraw
  - `retry_from_02b` – wróć do AI #2b i popraw
  - `abort` – zatrzymaj łańcuch, zgłoś człowiekowi

---

## Jak działa łańcuch (przetwarzanie)

Dla jednego zlecenia:

```
START ŁAŃCUCHA
  │
  ▼
[DANE ZLECENIA] (pełne dane z Kroku 4)
  │
  ▼
[Slot 02b] AI #2b → wycena + dni → output: "wycena_dni"
  │
  ▼
[Slot 02a] AI #2a → treść oferty (dostaje "wycena_dni") → output: "opis"
  │
  ▼
[Slot 03] Walidator → sprawdza "opis"
  │
  ├── PASS → leci dalej
  └── FAIL → retry od 02a (max 3 razy)
  │
  ▼
[Slot 04] Walidator → sprawdza całość
  │
  ├── PASS → ✅ ŁAŃCUCH OK
  └── FAIL → ❌ abort → człowiek decyduje
  │
  ▼
[Krok 6] WERYFIKACJA CZŁOWIEKA
```

> **Kolejność 02b → 02a (wycena przed treścią):** wycena liczy się z samych danych zlecenia, nie potrzebuje treści. Treść natomiast musi znać kwotę i dni, żeby wpisać je naturalnie w sekcji wyceny oferty. Dlatego najpierw 02b produkuje `wycena_dni`, potem 02a je konsumuje jako input (`requires: ["wycena_dni"]`) i nie zmienia kwoty.

**Każde AI widzi:**
- Oryginalne dane zlecenia (zawsze dostępne)
- Outputy wszystkich poprzednich slotów (po kluczach)
- Swój własny prompt (jeśli ma `prompt_file`)
- Dodatkowe pliki (jeśli ma `context_files`)

**Retry:** jeśli validator da FAIL i `on_fail: "retry_from_*"`, łańcuch wraca do wskazanego generatora. Max 3 próby (`retry_max`). Po 3 failach – abort.

---

## Jak Playwright odpala łańcuch

```python
# Pseudokod – nie implementacja
def run_chain(zlecenie_dane, chain_config):
    context = {"zlecenie": zlecenie_dane}
    
    for slot in chain_config["slots"]:
        if not slot["enabled"]:
            continue
        
        prompt = read_file(f"prompts/{slot['prompt_file']}")
        lore = read_file("prompts/lore.md")
        
        response = deepseek_api.call(
            prompt=prompt,
            lore=lore,
            context=context
        )
        
        if slot["role"] == "generator":
            context[slot["output_key"]] = response
        
        elif slot["role"] == "validator":
            if response == "PASS":
                continue
            else:
                return handle_fail(slot, context, chain_config)
    
    return context  # zawiera "opis" i "wycena_dni" do formularza
```

---

## Przykładowe sloty (do wykorzystania)

| Slot | Nazwa | Rola | Co robi |
|---|---|---|---|
| 02a | Opis oferty | generator | Pisze treść propozycji |
| 02b | Wycena i dni | generator | Proponuje stawkę + liczbę dni |
| 03 | Walidator opisu | validator | Sprawdza czy opis pasuje do zlecenia |
| 04 | Spójność | validator | Sprawdza czy wycena pasuje do zakresu prac |
| 05 | Ton i styl | validator | Sprawdza czy ton pasuje do zleceniodawcy |
| 06 | Błędy językowe | validator | Sprawdza ortografię, gramatykę |
| 07 | Kompletność | validator | Sprawdza czy wszystkie wymagania pokryte |
| ... | ... | ... | ... |
| 20 | Ostatni rzut oka | validator | Końcowy przegląd całości |

---

## Zasady

1. **Jeden łańcuch = jedno zlecenie.** Nie mieszamy kontekstów między zleceniami.
2. **Sloty 01-20 są opcjonalne.** Domyślnie tylko 02a i 02b są enabled.
3. **Kolejność ma znaczenie.** Sloty są przetwarzane w kolejności z `chain_config.json`.
4. **Validator FAIL nie kasuje outputu.** Output generatora zostaje w kontekście, validator tylko blokuje przejście dalej.
5. **Pliki promptów to zwykłe `.md`.** Możesz je edytować w dowolnym edytorze tekstowym.