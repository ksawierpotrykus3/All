# PLAN REORGANIZACJI testy_camoufox
## [DATA] 2026-08-31 - [AKCJA] Projekt nowej struktury zgodnie z AGENTS.md

### 🎯 **CEL REORGANIZACJI:**
Zgodnie z nakazami AGENTS.md:
1. ✅ **Uprościć strukturę** (maksimum 3-4 poziomy głębokości)
2. ✅ **Eliminować duplikacje** (jedno miejsce na każdą funkcję)
3. ✅ **Standaryzować nazewnictwo** (jasne konwencje)
4. ✅ **Wszystkie wyniki w docs/** (zgodnie z zasadami)
5. ✅ **Integrować z feedback loop** (nowa struktura → dokumentacja)

### 📊 **ANALIZA OBECNEJ STRUKTURY:**

#### **Przed porządkowaniem:**
```
testy_camoufox/
├── .bin/                    ❌ PUSTY - USUNIĘTY
├── analysis/                ❌ PUSTY - USUNIĘTY
├── benchmark/               ❌ PUSTY - USUNIĘTY
├── core/                    ✅ UŻYWANY (4 podkatalogi)
├── docs/                    ✅ UŻYWANY
├── flow_optimized_card_*.png ❌ ZŁE MIEJSCE - PRZENIESIONE
├── implementation/          ✅ UŻYWANY (4 podkatalogi)
├── node_modules/            🚨 WRAPLIWE (w .gitignore)
├── testing/                 ✅ UŻYWANY (35+ testów)
├── tools/                   ✅ UŻYWANY (60+ narzędzi)
├── wynik_flow_optimized.json ❌ ZŁE MIEJSCE - PRZENIESIONE
└── __pycache__/            ❌ CACHE - USUNIĘTY
```

#### **Po porządkowaniu (dziś):**
```
testy_camoufox/
├── core/                    ✅ CHECKOUT, CRYPTO, DETECTION, INCOGNIA
├── docs/                    ✅ ARCHIVES, LOGS, REFERENCES, REPORTS, SCREENSHOTS, SYNTHESIS
├── implementation/          ✅ BROWSER-PROFILES, CURL-CFFI, HYBRID, PLAYWRIGHT
├── node_modules/            🚨 W .GITIGNORE (ok)
├── testing/                 ✅ 35+ TESTÓW + 4 PODKATALOGI
└── tools/                   ✅ 60+ NARZĘDZI + 4 PODKATALOGI
```

### 🔍 **PROBLEMY DO ROZWIĄZANIA (jutro):**

#### **Problem 1: Duplikacja funkcji**
```python
duplication_issues = {
    "testing/probes": "Podobne funkcje co tools/analysis",
    "tools/debugging": "Nakłada się z tools/analysis", 
    "tools/capture": "Podobne do testing/diagnostics",
    "core/ vs implementation/": "Niejasny podział - oba mają checkout"
}
```

#### **Problem 2: Zbyt głęboka struktura**
```python
depth_issues = {
    "tools/extraction/": "3 poziomy głębokości",
    "implementation/browser-profiles/": "3 poziomy",
    "testing/diagnostics/": "3 poziomy",
    "docs/synthesis/": "3 poziomy (ok)"
}
```

#### **Problem 3: Niejasny podział odpowiedzialności**
```python
responsibility_issues = {
    "core/checkout": "Core logic checkout",
    "implementation/curl-cffi": "Implementation checkout",
    "testing/": "Tests for checkout",
    "tools/": "Tools for checkout",
    "problem": "Checkout rozrzucone w 4 miejscach"
}
```

### 🎯 **PROJEKT NOWEJ STRUKTURY:**

#### **Zasady projektowe:**
1. **Maksimum 3 poziomy głębokości**
2. **Jeden główny folder na moduł** (checkout, detection, etc.)
3. **Wszystkie wyniki w docs/** (logs, reports, results)
4. **Testy i narzędzia razem** przy modułach
5. **Brak duplikacji** funkcji

#### **Proponowana struktura:**
```
testy_camoufox/
├── checkout/                    # Wszystko dot. checkout w jednym miejscu
│   ├── core/                   # Core logic (z core/checkout)
│   ├── implementation/         # Implementations (z implementation/)
│   ├── tests/                  # Tests (z testing/)
│   └── tools/                  # Tools (z tools/)
├── detection/                  # Wszystko dot. detection
│   ├── core/                   # (z core/detection)
│   ├── tests/                  # (z testing/)
│   └── tools/                  # (z tools/)
├── incognia/                   # Wszystko dot. incognia
│   ├── core/                   # (z core/incognia)
│   ├── implementation/         # (z implementation/)
│   ├── tests/                  # (z testing/)
│   └── tools/                  # (z tools/)
├── crypto/                     # Wszystko dot. crypto
│   ├── core/                   # (z core/crypto)
│   ├── tests/                  # (z testing/)
│   └── tools/                  # (z tools/)
├── shared/                     # Współdzielone komponenty
│   ├── browser-profiles/       # (z implementation/browser-profiles)
│   ├── utilities/              # Wspólne narzędzia
│   └── libraries/              # Biblioteki (curl-cffi, playwright)
└── docs/                       # Dokumentacja (bez zmian)
    ├── logs/                   # Wszystkie logi
    ├── reports/                # Wszystkie raporty
    ├── results/                # Wszystkie wyniki
    ├── screenshots/            # Screenshots
    ├── synthesis/              # Syntezy dokumentacyjne
    └── archives/               # Archiwa
```

### 📅 **HARMONOGRAM REORGANIZACJI:**

#### **Etap 2: Analiza i projekt (jutro - 2026-09-01)**
1. 🔄 **Analiza importów** - które pliki są rzeczywiście używane
2. 🔄 **Mapa dependencies** między modułami
3. 🔄 **Projekt nowej struktury** (ten dokument)
4. 🔄 **Plan migracji** krok po kroku

#### **Etap 3: Implementacja (pojutrze - 2026-09-02)**
1. 🔄 **Migracja checkout** do jednego folderu
2. 🔄 **Migracja detection** do jednego folderu  
3. 🔄 **Migracja incognia** do jednego folderu
4. 🔄 **Migracja crypto** do jednego folderu
5. 🔄 **Utworzenie shared/** dla współdzielonych komponentów
6. 🔄 **Aktualizacja importów** we wszystkich plikach

#### **Etap 4: Walidacja (2026-09-03)**
1. 🔄 **Testowanie nowej struktury** - czy wszystko działa [POTWIERDZONE]
2. 🔄 **Update dokumentacji** - nowe ścieżki
3. 🔄 **Cleanup** - usunięcie starych, nieużywanych plików
4. 🔄 **Finalny raport** - dokumentacja reorganizacji

### 🔄 **INTEGRACJA Z FEEDBACK LOOP:**

#### **Workflow reorganizacji:**
```
ODKRYCIE NIEPORZĄDKU → DOKUMENTACJA → KONFRONTACJA → 
→ [KONFLIKT] Struktura vs Zasady → 
→ ROZSZERZENIE BADAŃ (analiza użycia) → 
→ NOWY PLAN (ten dokument) → 
→ IMPLEMENTACJA (reorganizacja) → 
→ DOKUMENTACJA (nowa struktura) → 
→ ROZSTRZYGNIĘCIE (system uporządkowany)
```

### 📋 **CHECKLISTA SUKCESU:**

#### **Kryteria sukcesu nowej struktury:**
- [ ] **Maksimum 3 poziomy głębokości** (obecnie: 4-5)
- [ ] **Jeden folder na moduł** (obecnie: rozrzucone w 4 miejscach)
- [ ] **Brak duplikacji funkcji** (obecnie: wiele duplikatów)
- [ ] **Wszystkie wyniki w docs/** (obecnie: rozrzucone)
- [ ] **Standaryzowane nazewnictwo** (obecnie: mieszane)
- [ ] **Wszystkie testy działają** (obecnie: tak, musi pozostać)
- [ ] **Importy zaktualizowane** (obecnie: muszą działać)

### 🛠️ **NARZĘDZIA DO UŻYCIA:**

#### **Do analizy:**
1. `python dependency_analyzer.py` - analiza importów
2. `python file_usage_analyzer.py` - które pliki są używane
3. `python structure_validator.py` - walidacja nowej struktury

#### **Do migracji:**
1. `python migration_tool.py` - automatyczna migracja plików
2. `python import_updater.py` - aktualizacja importów
3. `python test_runner.py` - testowanie po migracji

---

**SYGNATURA:** Agent AI - plan reorganizacji zgodnie z AGENTS.md  
**DATA:** 2026-08-31  
**STATUS:** Etap 1 ukończony (natychmiastowe porządkowanie)  
**NASTĘPNY KROK:** Etap 2 - analiza użycia i projekt nowej struktury  
**ZGODNOŚĆ:** ✅ Pełna zgodność z nakazami AGENTS.md