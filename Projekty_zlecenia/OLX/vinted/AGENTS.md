# AGENTS.md — BIBLIA AGENTÓW AI VINTED BOT

## 🎯 **MISJA I CEL**

**Projekt:** Vinted Bot - Automatyczny system zakupów na Vinted.pl  
**Cel:** Pokonać kops.gg (<1s detection, <4s checkout) przy 50% niższych kosztach  
**Status:** W TRAKCIE - kluczowe blokery nierozwiązane  

---

## 📁 **STRUKTURA PROJEKTU - MAPA INFORMACJI**

### **ROOT - GŁÓWNE PLIKY:**
```
AGENTS.md                    ← TEN PLIK - biblia agentów
.gitignore                   # Wrażliwe dane NIGDY do repo
cleanup_sensitive_data.py    # Narzędzie do czyszczenia
```

### **BOT/ - Prototyp MVP:**
```
bot/src/vintedbot/           # Kod produkcyjny
bot/tests/                   # Testy jednostkowe
bot/scripts/                 # Skrypty pomocnicze
```

### **VINTED/ - Badania i rozwój:**
```
vinted/
├── dane/                    # DOWODY (najważniejsze!)
│   ├── captured_requests.json  # ✅ RZECZYWISTE requesty HTTP
│   ├── captured_api_paths.json # ✅ Endpointy z analizy
│   └── *.txt/*.json         # Logi, cookies, sesje (WRAPLIWE!)
├── narzedzia/               # Narzędzia badawcze
├── raporty/                 # ANALIZY I RAPORTY
└── testy_camoufox/          # TESTY CAMOUFOX (główny front)
```

### **DOCS/ - Dokumentacja:**
```
docs/superpowers/           # Plany i specyfikacje
```

---

## 🧠 **HIERARCHIA PRAWDY - CO JEST WIARYGODNE?**

### **RANGA 1: Twarde dowody (NAJWYŻSZA wiarygodność)**
```
✅ vinted/dane/captured_requests.json   # Rzeczywiste HTTP requests
✅ vinted/dane/captured_api_paths.json  # Endpointy z analizy
✅ *.log z timestampami                 # Logi wykonania testów
✅ *.json z wynikami testów             # Pomiarowe dane
```

### **RANGA 2: Analiza istniejących danych (WYSOKA)**
```
✅ Reverse engineering kodu JS          # Analiza frontendu Vinted
✅ HAR files (*.har)                    # Przechwycone sesje
✅ Porównanie z logami                  # Cross-reference
```

### **RANGA 3: Eksperckie oceny (ŚREDNIA)**
```
⚠️ Analiza konkurencji (kops.gg)       # Research rynkowy
⚠️ Ocena biznesowa                      # Estymacje kosztów
⚠️ Estymacje czasów                    # Przewidywania
```

### **RANGA 4: Hipotezy i spekulacje (NISKA)**
```
❌ AI-generated research               # Wygenerowane przez modele
❌ Marketingowe deklaracje             "checkout 0.6-1.2s"
❌ Spekulacje bez dowodów              "Portfel omija 3DS"
```

---

## 🚫 **ZAKAZANE ZACHOWANIA - ABSOLUTNY ZAKAZ**

### **1. NIGDY nie dodawaj wrażliwych danych do git:**
```bash
# ❌ ABSOLUTNY ZAKAZ:
git add cookies_*.txt
git add *_session*.json  
git add *token*.js
git add *.env

# ✅ Poprawnie:
# Wszystkie wrażliwe dane w .gitignore
# Branch tylko lokalny dla testów
```

### **2. NIGDY nie traktuj hipotez jako faktów:**
```markdown
# ❌ ZAKAZANE:
"Checkout jest 100% zweryfikowany" (bez captured_requests)
"Endpointy transakcji działają" (tylko w AI research)

# ✅ POPRAWNIE:
"[HIPOTEZA] Checkout prawdopodobnie używa /checkout/build"
"[NIEPOTWIERDZONE] Endpointy transakcji wymagają weryfikacji"
```

### **3. NIGDY nie usuwaj oryginalnych danych:**
```bash
# ❌ ZAKAZANE:
rm captured_requests.json
delete *.log files
overwrite original test results

# ✅ POPRAWNIE:
Archive old files
Create synthesis documents
Keep originals as reference
```

### **4. NIGDY nie zmyślaj pomiarów:**
```python
# ❌ ZAKAZANE:
wynik = {"checkout_time": "0.8s"}  # bez rzeczywistego pomiaru
# ✅ POPRAWNIE:  
wynik = {"checkout_status": "403 Blocked"}  # rzeczywisty wynik
```

---

## ✅ **WYMAGANE ZACHOWANIA - ZASADY AGENTÓW**

### **1. ZAWSZE sprawdzaj captured_requests.json:**
```python
# Przed twierdzeniem o endpointach:
def verify_endpoint_exists(endpoint_name):
    with open('vinted/dane/captured_requests.json') as f:
        data = json.load(f)
        return any(endpoint_name in req['url'] for req in data)
    
# Przykład użycia:
if not verify_endpoint_exists('checkout/build'):
    print("[HIPOTEZA] Endpoint checkout/build wymaga weryfikacji")
```

### **2. ZAWSZE oznaczaj poziom pewności:**
```markdown
# W dokumentacji:
[UDOWODNIONE] Rate-limit Vinted: ~0.83 req/s (captured_requests.json)
[POTWIERDZONE] kops.gg detekcja ~2.3s, checkout 5-6s (analiza logów)
[DOMNIEMANE] Checkout flow używa 2 requestów (analiza JS)
[NIEPOTWIERDZONE] Portfel omija 3DS (AI research bez dowodów)
```

### **3. ZAWSZE podawaj źródła:**
```markdown
## Źródła:
- `captured_requests.json` linie 45-67
- `testy_camoufox/docs/logs/bench_out.txt`
- `vinted/dane/vinted_real_endpoints.json`
- Analiza kodu: `checkout/build` w zminifikowanym JS
```

### **4. ZAWSZE aktualizuj syntezy po nowych danych:**
```
NOWE DANE → Sprawdź konflikty → Zaktualizuj syntezy → Oznacz w 00_POWTORZENIA...
```

### **5. [NAKAZ] TWÓRZ DOKUMENTACJĘ przy nowych odkryciach:**
```python
# NAKAZ: Każde nowe odkrycie → nowa dokumentacja
def document_new_discovery(discovery_type, evidence, confidence_level):
    """
    NAKAZ: Każde nowe odkrycie musi być udokumentowane.
    
    discovery_type: "endpoint", "bug", "workaround", "limitation"
    evidence: captured_requests.json entry, logs, screenshots
    confidence_level: "UDOWODNIONE", "POTWIERDZONE", "DOMNIEMANE"
    """
    # 1. Zapis do captured_requests.json jeśli to endpoint
    # 2. Utworzenie nowego raportu w odpowiednim folderze
    # 3. Aktualizacja syntez w testy_camoufox/docs/synthesis/
    # 4. Oznaczenie w 00_POWTORZENIA_I_SPRZECZNOSCI.md jeśli konflikt
```

### **6. [NAKAZ] KONFRONTACJA z dokumentacją przy konfliktach:**
```
SCHEMAT KONFRONTACJI:

KONFLIKT WYKRYTY → SPRAWDŹ captured_requests.json → 
→ JEŚLI BRAK DOWODÓW → OZNACZ JAKO [HIPOTEZA]
→ JEŚLI SPRZECZNE DOWODY → ROZSZERZ BADANIA
→ JEŚLI POTWIERDZONE → AKTUALIZUJ WSZYSTKIE DOKUMENTY
```

### **7. [NAKAZ] ROZSZERZANIE BADAŃ i testów przy konfliktach:**
```markdown
# NAKAZ: Konflikt = wymóg rozszerzenia badań

## Przykład konfliktu checkout:
[SPRZECZNOŚĆ]
- Źródło A: "Checkout 100% zweryfikowany"
- Źródło B: "Brak endpointów w captured_requests"

[NAKAZ ROZSZERZENIA BADAŃ]
1. **Wymagany nowy test:** Przechwycenie checkout flow z Camoufox
2. **Wymagane dane:** captured_requests z rzeczywistymi requestami
3. **Wymagana dokumentacja:** Szczegółowy raport z timestampami
4. **Wymagana weryfikacja:** HTTP 200 z zakupem lub HTTP status z przyczyną
```

### **8. [NAKAZ] KONWENCJA COMMITÓW (Conventional Commits):**

```
<type>(<scope>): <description>

[optional body]
[optional footer(s)]
```

**Dozwolone `<type>`:**
| type | kiedy | przykład |
|------|-------|----------|
| `feat` | nowa funkcja/odkrycie | `feat(checkout): add JWE token generator` |
| `fix` | poprawka błędu | `fix(api): correct DataDome header order` |
| `docs` | tylko dokumentacja | `docs(synteza): update CHECKOUT_KONFLIKTY.md` |
| `chore` | porządki, deps, config | `chore(archive): git mv validate_*.py` |
| `refactor` | restrukturyzacja bez zmiany zachowania | `refactor(tools): dedupe analyze_har scripts` |
| `test` | nowe testy | `test(checkout): add 403 diagnostic probe` |
| `revert` | cofanie zmiany | `revert: feat(checkout) - rollback 403 regression` |

**`<scope>` (opcjonalny):** `bot`, `testy_camoufox`, `incognia`, `checkout`, `synteza`, `raporty`, `archive`, `ci`.

**Wymagania:**
- opis w trybie rozkazującym, małe litery, bez kropki na końcu
- max 72 znaki w pierwszej linii
- body oddzielone pustą linią (jeśli >1 linia)
- footer `Refs: #123` lub `Breaking-Change:` jeśli dotyczy

**Przykłady z historii projektu:**
```
✅ chore(archive): git mv validate_new_mandates.py to archive
✅ feat(tools): add validate_confidence_tags.py — scan .md for untagged claims
✅ chore(testy_camoufox): add pyproject.toml with detected deps
❌ "poprawki" (za ogólne)
❌ "WIP" (bez typu i opisu)
```

---

## 🗺️ **MAPY I SCHEMATY**

### **Mapa wiedzy projektu:**
```
┌─────────────────────────────────────────────────────────────┐
│                     CO WIEMY (FACTS)                         │
│  ✅ API katalogu działa (catalog/items)                      │
│  ✅ Rate-limit: 0.83 req/s                                   │
│  ✅ ID ofert losowe (nieprzewidywalne)                       │
│  ✅ DataDome ROZWIĄZANY: slider solver + profil_firefox_135  │
│  ✅ build=200 deterministycznie (25/25 testów, 2026-09-02)   │
│  ✅ kops.gg detekcja ~2.3s (checkout 5-6s, nie <1s)          │
├─────────────────────────────────────────────────────────────┤
│                     CO NIE WIEMY (GAPS)                      │
│  ❓ Payment=200 (brak karty na koncie testowym, err 114)     │
│  ❓ TTL odblokowania DataDome (ile trzyma cookie)            │
│  ❓ 3DS/BLIK w runtime (nietestowane)                        │
└─────────────────────────────────────────────────────────────┘
```

### **Schemat workflow agenta:**
```
1. PRZED DZIAŁANIEM:
   ↓
2. SPRAWDŹ captured_requests.json
   ↓
3. SPRAWDŹ logi testów (*.log, *.json)
   ↓  
4. SPRAWDŹ konflikty w 00_POWTORZENIA...
   ↓
5. OZNACZ poziom pewności ([UDOWODNIONE]/[HIPOTEZA])
   ↓
6. DZIAŁAJ (testy, analiza, kod)
   ↓
7. ZAPISZ wyniki (logi, JSON, captured_requests)
   ↓
8. [NAKAZ] TWÓRZ DOKUMENTACJĘ dla nowych odkryć
   ↓
9. AKTUALIZUJ syntezy i dokumentację
   ↓
10. [NAKAZ] KONFRONTACJA z istniejącą dokumentacją
   ↓
11. JEŚLI KONFLIKT → [NAKAZ] ROZSZERZ BADANIA
   ↓
12. SPRAWDŹ konflikty (00_POWTORZENIA...) - aktualizuj
```

---

## 🔍 **KRYTYCZNE PLIKI I ICH ZNACZENIE**

### **vinted/dane/captured_requests.json**
```json
{
  "url": "/api/v2/catalog/items",
  "method": "GET",
  "status": 200,
  "timestamp": "2026-08-28T10:30:00"
}
```
**Znaczenie:** Rzeczywiste requesty HTTP do Vinted. Jeśli czegoś tu nie ma = nie udowodnione.

### **vinted/raporty/00_POWTORZENIA_I_SPRZECZNOSCI.md**
**Znaczenie:** Rejestr wszystkich konfliktów i sprzeczności. Jeśli coś jest tu oznaczone = wymaga rozstrzygnięcia.

### **testy_camoufox/docs/synthesis/**
**Znaczenie:** JEDYNA wersja prawdy. Aktualny status projektu w syntezach tematycznych.

### **.gitignore**
**Znaczenie:** Lista wrażliwych plików które NIGDY nie mogą trafić do repo git.

---

## 🔬 **[NAKAZ] WYMOGI ROZSZERZANIA BADAŃ**

### **Kiedy ROZSZERZASZ badania (obowiązkowe):**
1. **KONFLIKT w dokumentacji** - rozszerz badania żeby rozstrzygnąć
2. **BRAK captured_requests** dla twierdzeń - zrób testy żeby zdobyć dowody
3. **HIPOTEZA bez testów** - zaprojektuj i wykonaj eksperyment
4. **NOWY BLOKER** (np. DataDome 403) - systematycznie testuj workaroundy

### **Minimalne wymagania dla rozszerzonych badań:**
```python
# WYMÓG: Każde rozszerzone badanie musi zawierać:
research_requirements = {
    "hypothesis": "Czy checkout używa endpointów /checkout/build?",
    "test_design": "Test z Camoufox + pełne logowanie network",
    "data_collection": "captured_requests.json + logs z timestampami",
    "minimum_tests": 3,  # Minimum 3 niezależne testy
    "success_criteria": "Przechwycone requesty checkout lub HTTP 403 z przyczyną",
    "documentation": "Nowy raport w docs/synthesis/ + aktualizacja syntez"
}
```

### **Procedura rozszerzania badań:**
```
1. IDENTYFIKUJ konflikt lub lukę w wiedzy
2. ZAPROJEKTUJ testy żeby zdobyć brakujące dowody
3. WYKONAJ minimum 3 niezależne eksperymenty
4. ZAPISZ wszystkie dane (captured_requests, logs)
5. DOKUMENTUJ wyniki w syntezach
6. AKTUALIZUJ 00_POWTORZENIA... z rozstrzygnięciem
```

---

## 🚨 **ALERTY I BŁĘDY**
```bash
# 1. Brak captured_requests dla twierdzeń o endpointach
# 2. Dokumentacja mówi "100%" ale logs pokazują 403
# 3. Duplikaty wrażliwych danych w git
# 4. AI research traktowany jako fact
```

### **Żółte flagi (OSTRZEŻENIE - sprawdź):**
```bash
# 1. Nowe endpointy bez weryfikacji w captured_requests
# 2. Czasy <1s bez logów timestampów  
# 3. Dokumenty w 07_niezweryfikowane/ używane jako źródło
# 4. Brak oznaczenia [UDOWODNIONE]/[HIPOTEZA]
# 5. Burst równoległych żądań >1 req/s — regresja P2 łamie rate-limit Vinted
```

---

## 🛠️ **NARZĘDZIA DLA AGENTÓW**

### **1. Weryfikacja faktów:**
```bash
# Sprawdź czy endpoint istnieje w captured_requests
grep -i "checkout" vinted/dane/captured_requests.json

# Sprawdź logi testów
tail -n 50 vinted/testy_camoufox/docs/logs/*.log

# Sprawdź konflikty w dokumentacji
python vinted/testy_camoufox/tools/manage_documentation_conflicts.py --report
```

### **2. Zarządzanie dokumentacją:**
```bash
# Aktualizuj syntezę po nowych danych
# 1. Edytuj odpowiedni plik w docs/synthesis/
# 2. Sprawdź konflikty w 00_POWTORZENIA...
# 3. Zaktualizuj SYNTEZA_GŁÓWNA.md

# [NAKAZ] Tworzenie nowej dokumentacji
python vinted/testy_camoufox/tools/manage_documentation_conflicts.py --report
# Sprawdź konflikty → Zidentyfikuj luki → Zaprojektuj badania
```

### **3. Rozszerzanie badań (konflikt-driven):**
```bash
# [NAKAZ] Gdy konflikt → rozszerz badania
# 1. Znajdź konflikt w 00_POWTORZENIA...
grep -n "Sprzeczność" vinted/raporty/00_POWTORZENIA_I_SPRZECZNOSCI.md

# 2. Sprawdź czy są dowody w captured_requests
grep -i "checkout" vinted/dane/captured_requests.json | wc -l

# 3. Jeśli brak dowodów → zaprojektuj testy
#    - Nowy skrypt testowy w testy_camoufox/
#    - Full network logging
#    - Minimum 3 niezależne testy

# 4. Wykonaj testy i zapisz dowody
#    - captured_requests.json append
#    - Nowe logs w testy_camoufox/docs/logs/
```

### **4. Wykorzystywanie serwerów MCP:**
```bash
# [NAKAZ] Sprawdź dostępne serwery MCP przed działaniem
# Dostępne serwery MCP w tym projekcie (wywoływane przez narzędzie run_mcp):
run_mcp(server_name="context7", tool_name="query-docs", args={"query": "..."})
# Dostępne serwery: context7, duckdb, memory, sequential-thinking, git, playwright
# UWAGA: przed wywołaniem odczytaj deskryptor narzędzia (LS + Read) w folderze MCP.

# Przykład użycia context7 dla Vinted Bot:
# - Dokumentacja curl_cffi dla TLS/JA4
# - Playwright API reference dla network interception
# - Porównanie bibliotek HTTP client
```

### **5. Bezpieczeństwo danych:**
```bash
# Sprawdź czy wrażliwe dane są ignorowane
git status --ignored | grep "cookies\|session\|token"

# Uruchom cleanup jeśli potrzeba
python cleanup_sensitive_data.py --check
```

---

## 📊 **STATUS PROJEKTU - KLUCZOWE METRYKI**

### **✅ UDOWODNIONE:**
| Metryka | Wartość | Źródło |
|---------|---------|---------|
| Rate-limit | 0.83 req/s | captured_requests.json |
| Max items/page | 96 | API tests |
| **Zasada: nigdy nie równoleglij żądań do Vinted ponad ~1 req/s** | regresja P2 | test1_determinizm (2026-09-02) |
| kops.gg detekcja | ~2.3s avg (checkout 5-6s) | analiza kops.gg |
| DataDome bypass | ROZWIĄZANY (slider) | build=200 25/25 (2026-09-02) |
| Checkout rezerwacja | ~3.51s avg (min 3.26s) | test1_determinizm_with_evidence_1788304069.json |
| Detekcja poll API | ~360 ms (WAW edge) | Telemetria v2 Waterfall |

### **❌ NIEUDOWODNIONE:**
| Element | Status | Problem |
|---------|--------|---------|
| Payment=200 | 400 error 114 | Brak karty/portfela na koncie testowym |
| TTL odblokowania DataDome | Niezmierzone | Cookie może wygasać |
| 3DS/BLIK | Hipoteza | Brak testów z prawdziwą kartą |

### **🎯 CELE:**
| Cel | Target | Status |
|-----|--------|--------|
| Detection time | <1.5s | ✅ ~0.36s zmierzone (2026-09-02) |
| Checkout time | <4s | ✅ ~3.51s avg do rezerwacji (min 3.36s, 5/5 build=200, 2026-09-02 z dowodami wizualnymi); full ~7.2s |
| Success rate | >90% | ⚠️ build/pickup 100% (25/25 prób live), payment 0% (brak karty) |
| Cost vs kops | 50% niższy | ✅ Potencjalnie |

---

## 🔗 **LINKI I REFERENCJE**

### **Dokumentacja główna:**
- [MENTAL_MAP_SYSTEM.md](MENTAL_MAP_SYSTEM.md) - Mapa wiedzy i skojarzeń
- [SYNTEZA_GŁÓWNA.md](vinted/testy_camoufox/docs/SYNTEZA_GŁÓWNA.md) - Status projektu
- [SYSTEM_DOKUMENTACJI.md](vinted/testy_camoufox/docs/SYSTEM_DOKUMENTACJI.md) - System zarządzania
- [00_POWTORZENIA_I_SPRZECZNOSCI.md](vinted/raporty/00_POWTORZENIA_I_SPRZECZNOSCI.md) - Konflikty

### **Narzędzia:**
- [manage_documentation_conflicts.py](vinted/testy_camoufox/tools/manage_documentation_conflicts.py) - Znajdowanie konfliktów
- [cleanup_sensitive_data.py](cleanup_sensitive_data.py) - Czyszczenie wrażliwych danych

### **Dane:**
- [captured_requests.json](vinted/dane/captured_requests.json) - Główne źródło prawdy
- [captured_api_paths.json](vinted/dane/captured_api_paths.json) - Endpointy

---

## 📞 **PROTOKÓŁ KOMUNIKACJI**

### **Kiedy zgłaszać problem:**
1. **Znaleziono sprzeczność** w dokumentacji → zgłoś w `00_POWTORZENIA...`
2. **Brak captured_requests** dla twierdzeń → zgłoś jako hipotezę
3. **Wrażliwe dane w git** → uruchom cleanup, zgłoś błąd

### **Format raportów:**
```markdown
## [DATA] - [AGENT_NAME] - [AKCJA]

### Co zrobiono:
- Test checkout z Camoufox
- Zapisywanie do captured_requests.json
- [NAKAZ] Dokumentacja nowych odkryć

### Wyniki:
- HTTP 403 DataDome (jak zawsze)
- Zapisano 3 nowe requesty do captured_requests
- [NAKAZ] Rozszerzenie badań: Zaprojektowano 3 nowe testy

### Źródła:
- captured_requests.json linie 150-180
- logs/checkout_test_2026-08-31.log
- Konflikt: 00_POWTORZENIA... linie 45-67

### Wnioski:
[UDOWODNIONE] DataDome nadal blokuje 403
[DOMNIEMANE] Checkout wymaga pełnego fingerprintu
[NAKAZ ROZSZERZENIA] Wymagane dodatkowe testy z różnymi fingerprintami

### Następne kroki (wymagane):
1. [NAKAZ] Rozszerz badania: Testy z pełnym fingerprint przeglądarki
2. [NAKAZ] Dokumentacja: Aktualizacja CHECKOUT_KONFLIKTY.md
3. [NAKAZ] Konfrontacja: Sprawdzenie sprzeczności w 00_POWTORZENIA...
```


---

## 🏁 **START HERE - DLA NOWYCH AGENTÓW**

### **Krok 1: Przeczytaj te pliki:**
1. ✅ **AGENTS.md** (ten plik) - zasady i struktura
2. ✅ **MENTAL_MAP_SYSTEM.md** - mapa wiedzy i skojarzeń
3. ✅ **SYNTEZA_GŁÓWNA.md** - status projektu
4. ✅ **00_POWTORZENIA_I_SPRZECZNOSCI.md** - konflikty do rozwiązania

### **Krok 1a (opcjonalnie - dla głębszego zrozumienia):**
5. 📖 **DOKUMENTACJA_INZYNIERSKA_CAMOUFOX.md** - główny dokument techniczny o Camoufox
6. 🔍 **SYNTEZA_CAMOUFOX_FIREFOX.md** - kluczowe odkrycia Camoufox w formie syntezy
7. 📊 **captured_requests.json** - źródło prawdy (requesty HTTP)

### **Krok 2: Sprawdź dane:**
1. ✅ **captured_requests.json** - co jest udowodnione
2. ✅ Logi testów w `testy_camoufox/docs/logs/`
3. ✅ **.gitignore** - czego NIE dotykać

### **🚀 EKSPRESOWE ONBOARDING (jeśli musisz zacząć szybciej):**
1. 📄 **AGENTS.md** (przeskanuj szybko) - zasady
2. 🧭 **MENTAL_MAP_SYSTEM.md** (przeczytaj triggery) - gdzie co jest
3. 🔍 **captured_requests.json** (sprawdź kluczowe endpointy) - źródło prawdy
4. ⚡ **DZIAŁAJ** - używaj mental map do wszystkiego

### **Krok 3: Działaj zgodnie z zasadami:**
1. ✅ ZAWSZE sprawdzaj captured_requests przed twierdzeniami
2. ✅ ZAWSZE oznaczaj poziom pewności ([UDOWODNIONE]/[HIPOTEZA])
3. ✅ NIGDY nie dodawaj wrażliwych danych do git
4. ✅ ZAWSZE aktualizuj syntezy po nowych danych
5. ✅ **[NAKAZ]** ZAWSZE twórz dokumentację przy nowych odkryciach
6. ✅ **[NAKAZ]** ZAWSZE konfrontuj z dokumentacją przy konfliktach
7. ✅ **[NAKAZ]** ZAWSZE rozszerzaj badania gdy brakuje dowodów
8. ✅ **[NAKAZ]** ZAWSZE sprawdzaj dostępne serwery MCP przed działaniem

### **Krok 4: Zgłaszaj się:**
- Konflikty → `00_POWTORZENIA_I_SPRZECZNOSCI.md`
- Nowe dane → odpowiednie syntezy w `docs/synthesis/`
- Błędy bezpieczeństwa → natychmiastowy cleanup
- **[NAKAZ]** Nowe odkrycia → nowa dokumentacja + testy
- **[NAKAZ]** Sprzeczności → rozszerzone badania + konfrontacja

---

**Ostatnia aktualizacja:** 2026-09-02  
**Wersja:** 1.0 - Biblia Agentów  
**Status systemu:** ✅ AKTYWNY - gotowy do użycia  
**Golden Rule:** **Jeśli nie ma w captured_requests.json = NIE JEST UDOWODNIONE**

---

## 🎯 **PODSUMOWANIE NOWYCH NAKAZÓW**

### **1. [NAKAZ] TWORZENIE DOKUMENTACJI:**
- **KAŻDE** nowe odkrycie → **NOWA dokumentacja**
- Bez dokumentacji = nie istnieje dla systemu
- Dokumentuj w: `docs/synthesis/` + `captured_requests.json`

### **2. [NAKAZ] KONFRONTACJA z dokumentacją:**
- **PRZED** działaniem → sprawdź konflikty w `00_POWTORZENIA...`
- **PO** odkryciu → skonfrontuj z istniejącą wiedzą
- **JEŚLI** sprzeczność → rozszerz badania

### **3. [NAKAZ] ROZSZERZANIE BADAŃ:**
- Konflikt = **WYMÓG** rozszerzenia badań
- **Minimum 3 niezależne testy** przy konfliktach
- **Full data collection**: captured_requests + logs + timestampy
- **Brak dowodów** = hipoteza wymagająca weryfikacji

### **4. [NAKAZ] WYKORZYSTYWANIE SERWERÓW MCP do rozszerzenia możliwości:**
```
# NAKAZ: ZAWSZE sprawdzaj dostępne serwery MCP przed działaniem

## Dostępne serwery MCP w projekcie:
1. **context7** - dokumentacje, API references, code examples
   - Użyj gdy: potrzebujesz aktualnej dokumentacji bibliotek/frameworków
   - Przykład: "curl_cffi documentation", "Playwright API reference"
2. **duckdb** - zapytania SQL do lokalnych danych pomiarowych
3. **memory** - graf wiedzy (encje, relacje, obserwacje)
4. **sequential-thinking** - rozkład złożonych problemów na kroki
5. **git** - status/diff/log bez konsoli
6. **playwright** - automatyzacja przeglądarki i zrzuty sieci

## Procedura użycia MCP:
PRZED DZIAŁANIEM → SPRAWDŹ listę dostępnych serwerów MCP → 
→ JEŚLI MCP SERWER ISTNIEJE → użyj run_mcp(server_name, tool_name, args) →
→ JEŚLI BRAK → DZIAŁAJ BEZ MCP

## Przykłady zastosowań MCP w Vinted Bot:
```python
# Zastosowanie context7 dla Vinted Bot:
mcp_use_cases = {
    "documentation": {
        "curl_cffi": "Aktualna dokumentacja TLS/JA4 fingerprint",
        "playwright": "API reference dla network interception",
        "python_requests": "Porównanie z curl_cffi"
    },
    "api_reference": {
        "vinted_api": "Jeśli istnieje oficjalna dokumentacja",
        "datadome_api": "Documentation DataDome bypass techniques",
        "payment_apis": "3DS, Adyen, payment gateways"
    },
    "code_examples": {
        "checkout_flow": "Przykłady implementacji checkout w innych projektach",
        "rate_limiting": "Best practices dla rate limiting avoidance",
        "proxy_rotation": "Code examples dla residential proxy rotation"
    }
}
```

## Wymagania użycia MCP:
1. ✅ **Sprawdź deskryptor narzędzia** przed wywołaniem (LS + Read w folderze MCP)
2. ✅ **Użyj** run_mcp(server_name, tool_name, args) zgodnie z dokumentacją
3. ✅ **Dokumentuj użycie MCP** w raportach - jakie narzędzia, jakie wyniki
4. ✅ **Nie nadużywaj** - MCP dla rzeczywistych potrzeb, nie dla każdego zapytania

### **5. [NAKAZ] CYBERNETYCZNY FEEDBACK LOOP z MCP:**
```
NOWE ODKRYCIE → SPRAWDŹ MCP → DOKUMENTACJA → KONFRONTACJA → 
→ JEŚLI KONFLIKT → UŻYJ MCP DO BADAŃ → ROZSZERZENIE BADAŃ → 
→ NOWE DANE → AKTUALIZACJA DOKUMENTACJI → ROZSTRZYGNIĘCIE KONFLIKTU
```

**System działa tylko jeśli:**  
✅ Dokumentacja jest aktualna  
✅ Konflikty są rozwiązywane  
✅ Badania są rozszerzane przy brakach  
✅ captured_requests.json jest źródłem prawdy  
✅ MCP serwery są wykorzystywane gdy dostępne

### **6. [NAKAZ] MENTAL MAP SYSTEM - eliminacja zgadywania:**
```
# NAKAZ: Żaden agent nigdy nie powinien się zastanawiać "gdzie co jest"

## System Mental Map:
1. 🧭 **MENTAL_MAP_SYSTEM.md** - główna mapa wiedzy
2. 🔗 **Skojarzeniowe triggery** - myślisz "checkout" → system prowadzi
3. 🗺️ **Mapa dokumentacji** - gdzie szukać konkretnych informacji
4. 🚨 **Automatyczne alerty** - ostrzeżenia dla kluczowych tematów

## Przykłady mental triggers:
[AGENT MENTAL TRIGGER: "checkout"] → SYNTEZA_CAMOUFOX_FIREFOX.md + captured_requests.json
[AGENT MENTAL TRIGGER: "DataDome"] → SYNTEZA_CAMOUFOX_FIREFOX.md sekcja Incognia
[AGENT MENTAL TRIGGER: "kops"] → SYNTEZA_GŁÓWNA.md metryki vs kops

## Zasady Mental Map:
1. ✅ ZAWSZE używaj mental map przed działaniem
2. ✅ NIGDY nie zgaduj "gdzie co jest" - sprawdź w mapie
3. ✅ AKTUALIZUJ mapę po nowych odkryciach
4. ✅ DODAJ nowe triggery gdy pojawia się nowy temat

## Link do Mental Map:
- [MENTAL_MAP_SYSTEM.md](MENTAL_MAP_SYSTEM.md) - główna mapa wiedzy
```

**System Mental Map działa tylko jeśli:**  
✅ Agent używa mapy przed każdym działaniem  
✅ Mapy są aktualizowane po nowych odkryciach  
✅ Brak zgadywania "gdzie co jest"  
✅ Skojarzeniowe triggery pokrywają wszystkie tematy