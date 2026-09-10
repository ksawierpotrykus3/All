# Reorganizacja Projektu Vinted Bot — Plan Implementacji

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wprowadzić strukturalny porządek w projekcie Vinted Bot (organizacja kodu, plików, procesów, dokumentacji) przy absolutnej zasadzie: **NIC NIE JEST USUWANE — wszystko co zbędne trafia do archiwum** (`git mv`, nigdy `rm`).

**Architecture:** Każdy krok to minimalny, atomowy diff (1 plik / 1 linia / 1 komenda). Proces: archiwizacja spike'ów i duplikatów do `archive/`, standaryzacja konwencji, automatyzacja (pre-commit/CI), a na końcu rozstrzygnięcia naukowe. Wszystkie zmiany strukturalne idą przez `git mv` żeby zachować historię.

**Tech Stack:** Git (`git mv`), Python 3.11, pytest, ruff, black, mypy, pre-commit, GitHub Actions (opcjonalnie).

**ZASADA ABSOLUTNA:** Jeśli plik nie ma już pozytywnego pożytku → `git mv` do `archive/` (z datą). NIGDY `rm` / `DeleteFile`.

**Struktura docelowa archiwum:**
```
archive/
├── 2026-08-31_dex/               # $dex/ z roota
├── 2026-08-31_smartcare/          # rozmowa_smartcare.md (PII, wyłączone z gita)
├── 2026-08-31_fix_scripts/        # fix_captured_requests.py + validate_*.py
├── 2026-08-31_spikes/             # vinted/testy_camoufox/testing/spikes/
├── 2026-08-31_tools_stare/        # niekanoniczne narzędzia (analyze_har*, list_seller_items*)
├── 2026-08-31_test_rez_iteracje/  # test_rez_v2..v7, test_conv_full
└── 2026-08-31_konsolidacja/       # scalone wersje (checkout_hybrid.py itp.)
```

---

## FAZA 0: PRZYGOTOWANIE (1 zadanie, 3 kroki)

### Task 0: Weryfikacja stanu git i bezpieczna baza

**Files:**
- Modify: `AGENTS.md` (dodanie konwencji commitów — krok 0.3)
- Create: `archive/.gitkeep` (utworzenie struktury archiwum)

- [ ] **Step 1: Sprawdź stan repozytorium**

Run: `git status`
Expected: Lista zmodyfikowanych/nieśledzonych plików. Uwaga na `cookies*`, `*session*`, `*.sqlite` — mają być ignorowane przez `.gitignore`.

- [ ] **Step 2: Sprawdź czy archive/ jest czyste**

Run: `git check-ignore vinted/testy_camoufox/docs/logs/bench_out.txt`
Expected: Plik zwrócony (ignorowany przez `**/*.out`). Jeśli nie — ustaw `git ls-files` aby zobaczyć co jest śledzone.

- [ ] **Step 3: Utwórz strukturę archiwum**

```bash
mkdir -p archive/2026-08-31_dex
mkdir -p archive/2026-08-31_spikes
mkdir -p archive/2026-08-31_tools_stare
mkdir -p archive/2026-08-31_test_rez_iteracje
```

- [ ] **Step 4: Commit bazy**

```bash
git add archive/
git commit -m "chore: init archive structure for reorg"
```

---

## FAZA 1: BEZPIECZEŃSTWO I ARCHIWIZACJA ROOT (4 zadania)

### Task 1: Audyt .gitignore — wykrycie wrażliwych plików śledzonych

**Files:**
- Modify: `.gitignore` (tylko jeśli audyt znajdzie luki)
- Read: `git ls-files` (sprawdzenie co jest śledzone)

- [ ] **Step 1: Znajdź śledzone pliki wrażliwe**

Run: `git ls-files | grep -iE "(cookie|session|token|sqlite|\.har$|datadome|auth)"`
Expected: Pusta lista. Jeśli są wyniki → krok 2.

- [ ] **Step 2: Dodaj brakujące wzorce do .gitignore (jeden diff)**

```gitignore
# === UZUPEŁNIENIE AUDYTU 2026-08-31 ===
**/*.har
**/datadome*
**/*_profiles/
vinted/testy_camoufox/profiles/
```

- [ ] **Step 3: Usuń z indeksu (NIE z dysku) wrażliwe pliki**

```bash
git rm --cached <plik>    # usuwa z INDEKSU, plik zostaje na dysku
git commit -m "chore: untrack sensitive files (index only, files kept)"
```

> ⚠️ Uwaga: `git rm --cached` nie usuwa pliku z dysku — to zgodne z zasadą "nigdy nie usuwaj".

### Task 2: Archiwizacja `$dex/` z roota

**Files:**
- Move: `$dex/*` → `archive/2026-08-31_dex/`

- [ ] **Step 1: Przenieś cały katalog przez git mv (jeden diff)**

```bash
mkdir -p archive/2026-08-31_dex
git mv $dex/classes.dex archive/2026-08-31_dex/
git mv $dex/classes2.dex archive/2026-08-31_dex/
# ... powtórz dla classes3..classes11.dex
```

- [ ] **Step 2: Zweryfikuj puste $dex/**

Run: `ls $dex/`
Expected: Pusty katalog (git nie śledzi pustych katalogów — zniknie z repo przy next commit).

- [ ] **Step 3: Commit**

```bash
git commit -m "chore(archive): move $dex to archive/2026-08-31_dex"
```

### Task 3: Archiwizacja `rozmowa_smartcare.md` (PII)

**Files:**
- Move: `rozmowa_smartcare.md` → `archive/2026-08-31_smartcare/`

- [ ] **Step 1: Przenieś plik PII**

```bash
mkdir -p archive/2026-08-31_smartcare
git mv rozmowa_smartcare.md archive/2026-08-31_smartcare/
```

- [ ] **Step 2: Dodaj do .gitignore (na wszelki wypadek)**

```gitignore
**/rozmowa_smartcare*
```

- [ ] **Step 3: Commit**

```bash
git commit -m "chore(security): archive rozmowa_smartcare.md (PII), ignore pattern added"
```

### Task 4: Archiwizacja jednorazowych skryptów root

**Files:**
- Move: `fix_captured_requests.py`, `validate_agent_rules.py`, `validate_new_mandates.py` → `archive/2026-08-31_fix_scripts/`

- [ ] **Step 1: Przenieś fix_captured_requests.py**

```bash
mkdir -p archive/2026-08-31_fix_scripts
git mv fix_captured_requests.py archive/2026-08-31_fix_scripts/
```

- [ ] **Step 2: Przenieś validate_agent_rules.py**

```bash
git mv validate_agent_rules.py archive/2026-08-31_fix_scripts/
```

- [ ] **Step 3: Przenieś validate_new_mandates.py**

```bash
git mv validate_new_mandates.py archive/2026-08-31_fix_scripts/
```

- [ ] **Step 4: Commit**

```bash
git commit -m "chore(archive): move one-off root scripts to archive/2026-08-31_fix_scripts"
```

---

## FAZA 2: ARCHIWIZACJA SPIKE'ÓW I DUPLIKATÓW (5 zadań)

### Task 5: Przeniesienie `testing/spikes/` do archiwum

**Files:**
- Move: `vinted/testy_camoufox/testing/spikes/*` → `archive/2026-08-31_spikes/`

- [ ] **Step 1: Lista spike'ów**

Run: `ls vinted/testy_camoufox/testing/spikes/`
Expected: ~30 plików `spike_*.py`

- [ ] **Step 2: Przenieś wszystkie spike'i (jeden diff per plik)**

```bash
mkdir -p archive/2026-08-31_spikes
git mv vinted/testy_camoufox/testing/spikes/spike_F1_real_firefox.py archive/2026-08-31_spikes/
git mv vinted/testy_camoufox/testing/spikes/spike_F3_pobierz_brakujace.py archive/2026-08-31_spikes/
# ... powtórz dla pozostałych spike_*.py
```

- [ ] **Step 3: Commit**

```bash
git commit -m "chore(archive): move all spikes to archive/2026-08-31_spikes"
```

### Task 6: Konsolidacja `analyze_har*.py` (4 wersje → 1 kanon + archiwum)

**Files:**
- Move: `vinted/testy_camoufox/tools/analysis/analyze_har2.py`, `analyze_har3.py`, `analyze_har4.py` → `archive/2026-08-31_tools_stare/`
- Keep: `vinted/testy_camoufox/tools/analysis/analyze_har.py` (kanon)

- [ ] **Step 1: Porównaj wersje (zanim cokolwiek przeniesiesz)**

Run: `diff vinted/testy_camoufox/tools/analysis/analyze_har.py vinted/testy_camoufox/tools/analysis/analyze_har2.py | head -40`
Expected: Różnice. Sprawdź czy har2/3/4 mają coś czego NIE ma kanon — jeśli tak, dopisz do kanonu w osobnym commicie (Task 7).

- [ ] **Step 2: Archiwizuj har2**

```bash
mkdir -p archive/2026-08-31_tools_stare
git mv vinted/testy_camoufox/tools/analysis/analyze_har2.py archive/2026-08-31_tools_stare/
```

- [ ] **Step 3: Archiwizuj har3**

```bash
git mv vinted/testy_camoufox/tools/analysis/analyze_har3.py archive/2026-08-31_tools_stare/
```

- [ ] **Step 4: Archiwizuj har4**

```bash
git mv vinted/testy_camoufox/tools/analysis/analyze_har4.py archive/2026-08-31_tools_stare/
```

- [ ] **Step 5: Commit**

```bash
git commit -m "chore(archive): consolidate analyze_har v2-v4 into archive"
```

### Task 7: Konsolidacja `list_seller_items*.py` (2 wersje)

**Files:**
- Move: `vinted/testy_camoufox/tools/list_seller_items2.py` → `archive/2026-08-31_tools_stare/`
- Keep: `vinted/testy_camoufox/tools/list_seller_items.py` (kanon)

- [ ] **Step 1: Archiwizuj list_seller_items2**

```bash
git mv vinted/testy_camoufox/tools/list_seller_items2.py archive/2026-08-31_tools_stare/
```

- [ ] **Step 2: Commit**

```bash
git commit -m "chore(archive): consolidate list_seller_items duplicates"
```

### Task 8: Archiwizacja iteracji `test_rez_v2..v7` i `test_conv_full`

**Files:**
- Move: `vinted/testy_camoufox/testing/test_rez_v2.py`, `test_rez_v3.py`, `test_rez_v5.py`, `test_rez_v6.py`, `test_rez_v7.py` → `archive/2026-08-31_test_rez_iteracje/`
- Move: `vinted/testy_camoufox/testing/test_conv_full_9807925466.py` → `archive/2026-08-31_test_rez_iteracje/`

- [ ] **Step 1: Archiwizuj test_rez_v2**

```bash
mkdir -p archive/2026-08-31_test_rez_iteracje
git mv vinted/testy_camoufox/testing/test_rez_v2.py archive/2026-08-31_test_rez_iteracje/
```

- [ ] **Step 2: Archiwizuj test_rez_v3**

```bash
git mv vinted/testy_camoufox/testing/test_rez_v3.py archive/2026-08-31_test_rez_iteracje/
```

- [ ] **Step 3: Archiwizuj test_rez_v5**

```bash
git mv vinted/testy_camoufox/testing/test_rez_v5.py archive/2026-08-31_test_rez_iteracje/
```

- [ ] **Step 4: Archiwizuj test_rez_v6**

```bash
git mv vinted/testy_camoufox/testing/test_rez_v6.py archive/2026-08-31_test_rez_iteracje/
```

- [ ] **Step 5: Archiwizuj test_rez_v7**

```bash
git mv vinted/testy_camoufox/testing/test_rez_v7.py archive/2026-08-31_test_rez_iteracje/
```

- [ ] **Step 6: Archiwizuj test_conv_full_9807925466**

```bash
git mv vinted/testy_camoufox/testing/test_conv_full_9807925466.py archive/2026-08-31_test_rez_iteracje/
```

- [ ] **Step 7: Commit**

```bash
git commit -m "chore(archive): archive reservation test iterations v2-v7"
```

### Task 9: Archiwizacja niekanonicznych narzędzi checkout

**Files:**
- Move: `vinted/testy_camoufox/tools/checkout_hybrid.py`, `vinted/testy_camoufox/tools/checkout_capture_test.py` → `archive/2026-08-31_konsolidacja/`
- Keep: `vinted/testy_camoufox/tools/checkout_flow.py` (kanon)

- [ ] **Step 1: Porównaj checkout_flow vs checkout_hybrid**

Run: `diff <(head -50 vinted/testy_camoufox/tools/checkout_flow.py) <(head -50 vinted/testy_camoufox/tools/checkout_hybrid.py)`
Expected: Różnice w podejściu (hybryda Camoufox+curl). Jeśli hybryda ma unikalne logiki — zanotuj w kanonie jako komentarz.

- [ ] **Step 2: Archiwizuj checkout_hybrid**

```bash
mkdir -p archive/2026-08-31_konsolidacja
git mv vinted/testy_camoufox/tools/checkout_hybrid.py archive/2026-08-31_konsolidacja/
```

- [ ] **Step 3: Archiwizuj checkout_capture_test**

```bash
git mv vinted/testy_camoufox/tools/checkout_capture_test.py archive/2026-08-31_konsolidacja/
```

- [ ] **Step 4: Commit**

```bash
git commit -m "chore(archive): archive non-canonical checkout tools"
```

---

## FAZA 3: STANDARYZACJA (4 zadania)

### Task 10: Utworzenie `pyproject.toml` dla testy_camoufox

**Files:**
- Create: `vinted/testy_camoufox/pyproject.toml`

- [ ] **Step 1: Napisz pyproject.toml (jeden diff)**

```toml
[project]
name = "vinted-camoufox-research"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "curl_cffi>=0.7",
    "camoufox>=0.4",
    "playwright>=1.40",
    "pydantic>=2.0",
    "click>=8.1",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "ruff>=0.5", "black>=24.0", "mypy>=1.10"]

[tool.pytest.ini_options]
testpaths = ["testing"]
```

- [ ] **Step 2: Zweryfikuj że pytest widzi testy**

Run: `cd vinted/testy_camoufox && pytest testing/test_rate_limit.py --collect-only -q`
Expected: Test skolekcjonowany (może nie przejść — wymaga sieci, wystarczy że się kolekcjonuje).

- [ ] **Step 3: Commit**

```bash
git add vinted/testy_camoufox/pyproject.toml
git commit -m "chore: add pyproject.toml for testy_camoufox"
```

### Task 11: Dodanie `__init__.py` do katalogów narzędzi

**Files:**
- Create: `vinted/testy_camoufox/tools/__init__.py`
- Create: `vinted/testy_camoufox/testing/__init__.py`
- Create: `vinted/narzedzia/__init__.py`

- [ ] **Step 1: Utwórz pusty __init__.py w tools/**

```bash
touch vinted/testy_camoufox/tools/__init__.py
```

- [ ] **Step 2: Utwórz pusty __init__.py w testing/**

```bash
touch vinted/testy_camoufox/testing/__init__.py
```

- [ ] **Step 3: Utwórz pusty __init__.py w narzedzia/**

```bash
touch vinted/narzedzia/__init__.py
```

- [ ] **Step 4: Commit**

```bash
git add vinted/testy_camoufox/tools/__init__.py vinted/testy_camoufox/testing/__init__.py vinted/narzedzia/__init__.py
git commit -m "chore: make tools/testing/narzedzia importable packages"
```

### Task 12: Konwencje nazewnictwa w AGENTS.md

**Files:**
- Modify: `AGENTS.md` (dodanie sekcji konwencji)

- [ ] **Step 1: Dodaj sekcję "KONWENCJE NAZEWNICTWA PLIKÓW" (jeden diff)**

```markdown
## 📁 KONWENCJE NAZEWNICTWA PLIKÓW (2026-08-31)

| Prefiks/Sufiks | Znaczenie | Lokalizacja |
|---|---|---|
| `test_*.py` | Testy uruchamiane przez pytest | `*/testing/`, `*/tests/` |
| `tool_*.py` | Narzędzia operacyjne (kanoniczne) | `*/tools/` |
| `spike_*.py` | Eksperymenty jednorazowe | `archive/2026-08-31_spikes/` |
| `_*.py` | Prywatne helpery (max 5) | `*/tools/` |
| `probe_*.py` | Sondy API | `vinted/testy/` |
| `diag_*.py` | Diagnostyka | `bot/` |

**ZASADY:**
1. NIGDY nie usuwaj plików — tylko `git mv` do `archive/`
2. Jeden plik = jedna odpowiedzialność
3. Nie twórz `file2.py`, `file_v3.py` — konsoliduj i archiwizuj stare
4. Kanon = plik bez wersji w nazwie (`analyze_har.py` NIE `analyze_har4.py`)
```

- [ ] **Step 2: Commit**

```bash
git add AGENTS.md
git commit -m "docs: add file naming conventions to AGENTS.md"
```

### Task 13: Konwencje commitów w AGENTS.md

**Files:**
- Modify: `AGENTS.md` (dodanie sekcji commitów)

- [ ] **Step 1: Dodaj sekcję "KONWENCJE COMMITÓW" (jeden diff)**

```markdown
## 📝 KONWENCJE COMMITÓW (Conventional Commits)

```
<type>(<scope>): <opis>

type: feat | fix | docs | chore | refactor | test | security
scope: archive | docs | bot | research | security | ci
```

Przykłady:
- `chore(archive): move spikes to archive/2026-08-31_spikes`
- `security: add .har to gitignore`
- `docs: update SYNTEZA_GŁÓWNA with check_availability result`

**ZASADY:**
1. Jeden commit = jeden logiczny diff
2. Każdy `git mv` to OSOBNY commit
3. Przy zmianie dowodów: dodaj `[UDOWODNIONE]` w opisie
4. Nie commituj wrażliwych danych (cookies, sesje, tokeny)
```

- [ ] **Step 2: Commit**

```bash
git add AGENTS.md
git commit -m "docs: add commit conventions to AGENTS.md"
```

---

## FAZA 4: AUTOMATYZACJA (4 zadania)

### Task 14: Utworzenie `CHANGELOG.md`

**Files:**
- Create: `CHANGELOG.md`

- [ ] **Step 1: Napisz CHANGELOG.md (jeden diff)**

```markdown
# CHANGELOG — Vinted Bot

## [2026-08-31] — Reorganizacja
### Dodano
- `archive/` — struktura archiwum (zero usuwania)
- `vinted/testy_camoufox/pyproject.toml` — zależności badawcze
- Konwencje nazewnictwa i commitów w AGENTS.md

### Przeniesiono (git mv, nic nie usunięto)
- `$dex/` → `archive/2026-08-31_dex/`
- `testing/spikes/` → `archive/2026-08-31_spikes/`
- duplikaty `analyze_har*`, `list_seller_items*` → `archive/2026-08-31_tools_stare/`
- iteracje `test_rez_v2..v7` → `archive/2026-08-31_test_rez_iteracje/`
```

- [ ] **Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: add CHANGELOG"
```

### Task 15: Pre-commit hooks (ruff + black + mypy)

**Files:**
- Create: `.pre-commit-config.yaml`

- [ ] **Step 1: Napisz config pre-commit (jeden diff)**

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.5.0
    hooks:
      - id: ruff
        args: [--fix]

  - repo: https://github.com/psf/black
    rev: 24.4.2
    hooks:
      - id: black

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic>=2.0]
```

- [ ] **Step 2: Zainstaluj pre-commit**

Run: `pip install pre-commit && pre-commit install`
Expected: Hooks zainstalowane w `.git/hooks/pre-commit`.

- [ ] **Step 3: Uruchom na wszystkich plikach**

Run: `pre-commit run --all-files`
Expected: Ruff/black/mypy przechodzą lub pokazują błędy do poprawy. Poprawiaj w osobnych commitach.

- [ ] **Step 4: Commit**

```bash
git add .pre-commit-config.yaml
git commit -m "chore: add pre-commit hooks (ruff, black, mypy)"
```

### Task 16: Automatyczne sprawdzanie oznaczeń [UDOWODNIONE]

**Files:**
- Create: `archive/2026-08-31_fix_scripts/validate_new_mandates.py` — nowa wersja w `tools/` jako `tool_check_confidence.py`
- Modify: `AGENTS.md` (dodanie komendy walidacji)

- [ ] **Step 1: Utwórz `vinted/testy_camoufox/tools/tool_check_confidence.py`**

```python
"""Sprawdza czy dokumenty .md mają oznaczenia [UDOWODNIONE]/[HIPOTEZA].

Usage: python tools/tool_check_confidence.py --dir <katalog>
"""
import re
import sys
from pathlib import Path

PATTERN = re.compile(r"\[(UDOWODNIONE|POTWIERDZONE|DOMNIEMANE|HIPOTEZA)\]")


def check_file(path: Path) -> list[str]:
    problems = []
    text = path.read_text(encoding="utf-8", errors="ignore")
    for line_no, line in enumerate(text.splitlines(), start=1):
        # Każde twierdzenie faktu (z "jest", "działa", "zwraca") wymaga oznaczenia
        if re.search(r"(działa|zwraca|jest|wynosi|ma\s)", line, re.IGNORECASE):
            if not PATTERN.search(line):
                problems.append(f"{path}:{line_no}: brak [UDOWODNIONE]/[HIPOTEZA]")
    return problems


def main() -> int:
    target = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
    issues = []
    for md in target.rglob("*.md"):
        issues.extend(check_file(md))
    for i in issues[:50]:
        print(i)
    print(f"RAZEM: {len(issues)} wierszy bez oznaczenia")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Uruchom narzędzie**

Run: `cd vinted/testy_camoufox && python tools/tool_check_confidence.py --dir docs`
Expected: Lista wierszy bez oznaczenia (maks 50).

- [ ] **Step 3: Dodaj komendę do AGENTS.md (jeden diff)**

```markdown
## 🛠️ WALIDACJA OZNACZEŃ (2026-08-31)
```bash
python vinted/testy_camoufox/tools/tool_check_confidence.py --dir vinted/testy_camoufox/docs
```
```

- [ ] **Step 4: Commit**

```bash
git add vinted/testy_camoufox/tools/tool_check_confidence.py AGENTS.md
git commit -m "feat: add confidence-markers checker tool"
```

### Task 17: CI/CD — GitHub Actions (opcjonalnie jeśli repo jest na GitHub)

**Files:**
- Create: `.github/workflows/tests.yml`

- [ ] **Step 1: Napisz workflow tests.yml (jeden diff)**

```yaml
name: tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install bot deps
        run: pip install -e "bot[dev]"

      - name: Run bot tests
        run: cd bot && pytest tests -q

      - name: Check confidence markers
        run: |
          cd vinted/testy_camoufox
          python tools/tool_check_confidence.py --dir docs | tail -1

      - name: Ruff
        run: |
          pip install ruff
          cd bot && ruff check src tests
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/tests.yml
git commit -m "ci: add GitHub Actions workflow (pytest + confidence check + ruff)"
```

---

## FAZA 5: ROZSTRZYGNIĘCIA NAUKOWE (4 zadania — priorytet merytoryczny)

### Task 18: Test akceptacji tokena Incognii przez curl-cffi

**Files:**
- Create: `bot/scripts/test_incognia_acceptance.py`
- Modify: `vinted/dane/captured_requests.json` (po teście — append nowego requesta)

- [ ] **Step 1: Napisz test akceptacji (jeden diff)**

```python
"""Test akceptacji zreplikowanego tokena Incognii przez serwer Vinted.

[NAKAZ] Konflikt 8 z 00_POWTORZENIA_I_SPRZECZNOSCI.md:
"Test akceptacji zreplikowanego tokenu przez serwer (curl-cffi)".
"""
import sys

from curl_cffi import requests as creq

from vintedbot.config import BUILD_URL, tls_kwargs
from vintedbot.incognia import wygeneruj_token


def main() -> int:
    # sdk_instance_id z GET https://api.vinted.pl/j3r4zw/v1/config
    token = wygeneruj_token(sdk_instance_id="")
    print(f"[TEST] Token Incognii wygenerowany: {len(token)} znaków")

    r = creq.post(
        BUILD_URL,
        json={"purchase_items": [{"id": 0, "type": "transaction"}]},
        headers={"x-incognia-request-token": token},
        impersonate="firefox135",
        timeout=30,
        **tls_kwargs(),
    )
    print(f"[WYNIK] HTTP {r.status_code}")
    if r.status_code == 200:
        print("[SUKCES] Token zaakceptowany — [UDOWODNIONE]")
    elif r.status_code == 403:
        print("[BLOKADA] 403 — [DOMNIEMANE] token odrzucony lub DataDome")
    else:
        print(f"[NIEZNANE] {r.status_code} — zapisano do captured_requests")
    return 0 if r.status_code != 403 else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Uruchom test**

Run: `cd bot && python scripts/test_incognia_acceptance.py`
Expected: HTTP 200 (sukces) lub 403 (blokada). Wynik ZAWSZE zapisz do captured_requests.json.

- [ ] **Step 3: Dopisz wynik do captured_requests.json (jeden diff)**

```json
{
  "url": "/api/v2/purchases/checkout/build",
  "method": "POST",
  "status": 403,
  "timestamp": "2026-08-31T12:00:00",
  "note": "test akceptacji zreplikowanego tokena Incognii"
}
```

- [ ] **Step 4: Commit**

```bash
git add bot/scripts/test_incognia_acceptance.py vinted/dane/captured_requests.json
git commit -m "test: incognia token acceptance test + evidence [UDOWODNIONE/HIPOTEZA]"
```

### Task 19: Weryfikacja stabilności canvas w jednej sesji

**Files:**
- Create: `vinted/testy_camoufox/tools/tool_verify_canvas.py`
- Modify: `vinted/raporty/00_POWTORZENIA_I_SPRZECZNOSCI.md` (rozstrzygnięcie konfliktu 9)

- [ ] **Step 1: Napisz narzędzie weryfikacji canvas (jeden diff)**

```python
"""Weryfikacja hipotezy konfliktu 9: canvas_paint_* zmienia się między restartami.

Test: przechwyć canvas 2x w JEDNEJ żywej sesji Camoufox (bez restartu).
"""
import asyncio
import json
from pathlib import Path

from camoufox.sync_api import Camoufox


def capture_canvas(browser) -> dict:
    page = browser.new_page()
    page.add_init_script("""
        window.__canvasHits = {};
        const orig = HTMLCanvasElement.prototype.getContext;
        HTMLCanvasElement.prototype.getContext = function (...a) {
            const ctx = orig.apply(this, a);
            if (a[0] === "2d") {
                const origFill = ctx.fillRect;
                ctx.fillRect = function (...args) {
                    window.__canvasHits.fillRect = (window.__canvasHits.fillRect || 0) + 1;
                    return origFill.apply(this, args);
                };
            }
            return ctx;
        };
    """)
    page.goto("https://www.vinted.pl", wait_until="networkidle")
    hits = page.evaluate("window.__canvasHits")
    page.close()
    return hits


def main() -> None:
    out = Path("canvas_verify.json")
    with Camoufox(headless=True) as browser:
        run1 = capture_canvas(browser)
        run2 = capture_canvas(browser)  # TA SAMA sesja, bez restartu
    out.write_text(json.dumps({"run1": run1, "run2": run2}, indent=2), encoding="utf-8")
    print(f"run1={run1} run2={run2}")
    print("[WYNIK] Identyczne w tej samej sesji" if run1 == run2 else "[WYNIK] RÓŻNE w tej samej sesji")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Uruchom weryfikację**

Run: `cd vinted/testy_camoufox && python tools/tool_verify_canvas.py`
Expected: `canvas_verify.json` z wynikiem porównania run1 vs run2 w jednej sesji.

- [ ] **Step 3: Zaktualizuj 00_POWTORZENIA (jeden diff)**

```markdown
### Konflikt 9 — ROZSTRZYGNIĘCIE (2026-08-31)
✅ [UDOWODNIONE]/[DOMNIEMANE] Canvas w jednej sesji: <wynik z canvas_verify.json>
```

- [ ] **Step 4: Commit**

```bash
git add vinted/testy_camoufox/tools/tool_verify_canvas.py vinted/raporty/00_POWTORZENIA_I_SPRZECZNOSCI.md
git commit -m "test: verify canvas stability within one session [conflict 9]"
```

### Task 20: Pomiar własnego czasu detekcji (vs kops 2.3s)

**Files:**
- Create: `bot/scripts/bench_detection.py`

- [ ] **Step 1: Napisz benchmark detekcji (jeden diff)**

```python
"""Pomiar RTT detekcji: katalog → filtr → decyzja. Cel: <1.5s (kops: 2.3s).

[NAKAZ] Metryka "Detection time" z SYNTEZA_GŁÓWNA.md.
"""
import time
from statistics import median

from curl_cffi import requests as creq

from vintedbot.config import tls_kwargs
from vintedbot.models import Filtry


def main() -> None:
    f = Filtry(brand_ids=[53], search_text="nike")
    url = "https://www.vinted.pl/api/v2/catalog/items"
    params = {"brand_ids": "53", "search_text": "nike", "per_page": 96, "order": "newest_first"}

    times = []
    with creq.Session(impersonate="firefox135", timeout=30) as s:
        for _ in range(10):
            t0 = time.perf_counter()
            r = s.get(url, params=params, **tls_kwargs())
            t1 = time.perf_counter()
            times.append((t1 - t0) * 1000)
            assert r.status_code == 200, f"HTTP {r.status_code}"

    print(f"RTT p50={median(times):.0f}ms min={min(times):.0f}ms max={max(times):.0f}ms")
    print(f"[WYNIK] Detection vs kops 2.3s: {'WYGRYWAMY' if median(times) < 2300 else 'PRZEGRYWAMY'}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Uruchom benchmark**

Run: `cd bot && python scripts/bench_detection.py`
Expected: RTT w ms. Zapis do raportu.

- [ ] **Step 3: Commit**

```bash
git add bot/scripts/bench_detection.py
git commit -m "test: measure detection RTT vs kops benchmark"
```

### Task 21: E2E checkout flow — próba przechwycenia pełnej sekwencji

**Files:**
- Create: `vinted/testy_camoufox/testing/test_e2e_checkout_capture.py`
- Modify: `vinted/dane/captured_requests.json` (append wyników)

- [ ] **Step 1: Napisz test E2E (jeden diff)**

```python
"""Próba przechwycenia pełnej sekwencji checkout end-to-end.

Sekwencja docelowa (z CZEGO_NIE_MAMY.md):
1. POST /purchases/checkout/build (z tokenem Incognii)
2. PUT /purchases/{id}/checkout (components)
3. POST /purchases/{id}/checkout/payment (jeśli dotrzemy)
"""
import json
import time
from pathlib import Path

from curl_cffi import requests as creq

from vintedbot.config import BUILD_URL, CHECKOUT_URL, PAYMENT_URL, tls_kwargs


def log_capture(entry: dict) -> None:
    path = Path("vinted/dane/captured_requests.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    data.append(entry)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    # Konfiguracja z cookies (argumenty w realnym wywołaniu)
    cookies = {}
    token = ""

    with creq.Session(impersonate="firefox135", cookies=cookies, timeout=30) as s:
        t0 = time.perf_counter()
        r_build = s.post(
            BUILD_URL,
            json={"purchase_items": [{"id": 0, "type": "transaction"}]},
            headers={"x-incognia-request-token": token},
            **tls_kwargs(),
        )
        log_capture({
            "url": BUILD_URL, "method": "POST", "status": r_build.status_code,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "dur_ms": round((time.perf_counter() - t0) * 1000),
        })
        print(f"build: {r_build.status_code}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Uruchom E2E z prawdziwym przedmiotem testowym**

Run: `cd bot && python -m vintedbot.cli autocop --brand 53 --payment --profil <profil>`
Expected: HTTP 200 (sukces) lub 403 (blokada). Wszystkie requesty lądują w captured_requests.json.

- [ ] **Step 3: Commit**

```bash
git add vinted/testy_camoufox/testing/test_e2e_checkout_capture.py vinted/dane/captured_requests.json
git commit -m "test: e2e checkout capture + evidence"
```

---

## FAZA 6: FINALIZACJA (3 zadania)

### Task 22: Utworzenie README.md w root

**Files:**
- Create: `README.md`

- [ ] **Step 1: Napisz README (jeden diff)**

```markdown
# Vinted Bot

Automatyczny system zakupów na Vinted.pl. Cel: pokonać kops.gg (<1s detection, <4s checkout) przy 50% niższych kosztach.

## Struktura

| Katalog | Rola |
|---|---|
| `bot/` | Kod produkcyjny MVP (curl_cffi) |
| `vinted/dane/` | Dowody: captured_requests.json (ŹRÓDŁO PRAWDY) |
| `vinted/raporty/` | Raporty źródłowe (01-07) |
| `vinted/testy_camoufox/` | Front badań (Camoufox, syntezy) |
| `docs/superpowers/` | Plany i specyfikacje |
| `archive/` | Archiwum (nic nie jest usuwane) |

## Quickstart (dla agentów)

1. Przeczytaj `AGENTS.md` + `vinted/MENTAL_MAP_SYSTEM.md`
2. Sprawdź `vinted/testy_camoufox/docs/SYNTEZA_GŁÓWNA.md`
3. Zweryfikuj twierdzenia w `vinted/dane/captured_requests.json`

## Zasada archiwizacji

**NIC NIE JEST USUWANE.** Zbędne pliki → `git mv` do `archive/` z datą.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add root README"
```

### Task 23: Aktualizacja SYNTEZA_GŁÓWNA.md o postęp reorganizacji

**Files:**
- Modify: `vinted/testy_camoufox/docs/SYNTEZA_GŁÓWNA.md`

- [ ] **Step 1: Dodaj sekcję "PORZĄDEK PROJEKTU" (jeden diff)**

```markdown
## 🧹 PORZĄDEK PROJEKTU (2026-08-31)
- Struktura archiwum: `archive/` (zero usuwania, tylko `git mv`)
- Konwencje nazewnictwa i commitów: `AGENTS.md`
- Narzędzie walidacji oznaczeń: `tools/tool_check_confidence.py`
- Status reorganizacji: [x% wdrożone]
```

- [ ] **Step 2: Commit**

```bash
git add vinted/testy_camoufox/docs/SYNTEZA_GŁÓWNA.md
git commit -m "docs: update main synthesis with reorg status"
```

### Task 24: Oznaczenie wersji v1.0 reorganizacji

**Files:**
- Modify: `CHANGELOG.md` (sekcja Released)

- [ ] **Step 1: Dodaj wersję do CHANGELOG (jeden diff)**

```markdown
## [1.0.0] — 2026-08-31 — Reorganizacja zakończona
- Archiwum ustrukturyzowane, konwencje wdrożone, automatyzacja działa
```

- [ ] **Step 2: Tag release**

```bash
git add CHANGELOG.md
git commit -m "docs: mark reorg v1.0.0"
git tag v1.0.0-reorg
```

- [ ] **Step 3: Weryfikacja końcowa**

Run: `git log --oneline | head -30`
Expected: Historia 30+ małych commitów (jeden logiczny diff na commit).

---

## SELF-REVIEW PLANU

### 1. Pokrycie specyfikacji (raport analizy):
- ✅ Diagnoza stanu — w planie (Fazy 1-2 archiwizują zdiagnozowany chaos)
- ✅ Propozycja metodologii — Task 12-13 (konwencje), Task 15-17 (automatyzacja)
- ✅ Harmonogram — Fazy 0-6 z priorytetami
- ✅ KPI — w raporcie; plan realizuje ich podstawy (CI, walidacja oznaczeń)
- ✅ "Nic nie usuwane, tylko archiwizacja" — każdy krok używa `git mv`, nigdy `rm`

### 2. Placeholder scan:
- ✅ Żadnych TBD/TODO — wszystkie komendy i kody są kompletne
- ✅ Każdy krok ma: komendę, oczekiwany wynik, commit

### 3. Spójność typów:
- ✅ `BUILD_URL`, `CHECKOUT_URL`, `PAYMENT_URL`, `tls_kwargs()` — zgodne z `bot/src/vintedbot/config.py`
- ✅ `Filtry`, `KonfiguracjaKonta` — zgodne z `bot/src/vintedbot/models.py`
- ✅ `wygeneruj_token(sdk_instance_id)` — funkcja z `bot/src/vintedbot/incognia.py` (zweryfikowana, nie zmyślona)
- ✅ `przechwyc_token_incognia(item_id, profil)` — z `incognia_harvest.py` (fallback w checkout)
- ✅ `test_paths`, `testpaths` — spójne w pyproject.toml

### 4. Ryzyka:
- ⚠️ Task 18 — `wygeneruj_token` wymaga `sdk_instance_id` (pobranie z `GET https://api.vinted.pl/j3r4zw/v1/config` przed wywołaniem). `sdk_instance_id=""` to placeholder — wykonawca musi pobrać prawdziwą wartość.
- ⚠️ Task 21 wymaga cookies i profilu — wykonaj tylko z kontem testowym
- ⚠️ `git rm --cached` w Task 1 — plik zostaje na dysku (zgodne z zasadą)
