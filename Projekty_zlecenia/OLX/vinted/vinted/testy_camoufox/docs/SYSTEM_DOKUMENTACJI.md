# SYSTEM ZARZĄDZANIA DOKUMENTACJĄ VINTED BOT

## 🎯 **CEL SYSTEMU**

Rozwiązywanie konfliktów i utrzymanie **jednej wersji prawdy** w dokumentacji projektu.

## 📁 **STRUKTURA SYSTEMU**

### 1. **ŹRÓDŁA ORYGINALNE** (niezmieniane)
```
raporty/
├── 01_sonda_api/          # Pomiary API - FAKTY
├── 02_reverse_engineering/ # Analiza kodu - HIPOTEZY  
├── 03_weryfikacja/        # Audyt - SPRAWDZENIE FAKTÓW
├── 04_niewiadome/         # Luki - CO NIE WIEMY
├── 05_konkurencja/        # Analiza rynku
├── 06_biznes/             # Wycena
└── 07_niezweryfikowane/   # AI research - NIEPOTWIERDZONE
└── 09_biezaca_sesja/      # Bieżące raporty statusowe sesji
```

### 2. **SYNTEZY** (aktualna prawda)
```
testy_camoufox/docs/
└── SYNTEZA_GŁÓWNA.md       # 🎯 GŁÓWNA SYNTEZA (KANONICZNA — jedyny egzemplarz)

testy_camoufox/docs/synthesis/
├── DETEKCJA_STATUS.md      # ✅ Co wiemy o detekcji
├── CHECKOUT_KONFLIKTY.md   # ⚠️ Sprzeczności checkout
├── KOPS_GG_ANALIZA.md      # 📊 Analiza konkurencji
└── SYNTEZA_CAMOUFOX_FIREFOX.md # 🔥 Kluczowe odkrycia Camoufox
```

### 3. **REJESTR KONFLIKTÓW**
```
raporty/00_POWTORZENIA_I_SPRZECZNOSCI.md
```
- Główny rejestr wszystkich konfliktów
- Mapuje sprzeczności między dokumentami
- Pokazuje rozstrzygnięcia

## 🔄 **PROCEDURA ROZWIĄZYWANIA KONFLIKTÓW**

### Krok 1: IDENTYFIKACJA
```bash
# Uruchom narzędzie do znajdowania konfliktów
cd F:\PROJEKTY\vinted
python vinted/testy_camoufox/tools/manage_documentation_conflicts.py --report
```

### Krok 2: ANALIZA
1. Sprawdź **captured_requests.json** - czy są dowody?
2. Sprawdź **logi testów** (*.log, *.json) - czy wykonano pomiary?
3. Sprawdź **analizę kodu** - czy to tylko hipoteza?

### Krok 3: ROZSTRZYGNIĘCIE
1. **Oznacz w `00_POWTORZENIA_I_SPRZECZNOSCI.md`:**
   ```
   ## Rozstrzygnięcie konfliktu X:
   - Źródło A: [stwierdzenie] ❌ FAŁSZ
   - Źródło B: [stwierdzenie] ✅ PRAWDA
   - Dowody: [link do captured_requests/logów]
   ```

2. **Zaktualizuj syntezy:**
   - `DETEKCJA_STATUS.md` - jeśli dotyczy detekcji
   - `CHECKOUT_KONFLIKTY.md` - jeśli dotyczy checkoutu
   - `SYNTEZA_GŁÓWNA.md` - ogólne podsumowanie

### Krok 4: ARCHIWIZACJA
- Oryginalne dokumenty **pozostają niezmienione**
- Tylko syntezy są aktualizowane
- Konflikty oznaczone jako "rozstrzygnięte"

## 🎯 **HIERARCHIA WIARYGODNOŚCI**

### Ranga 1: **NAJWYŻSZA** (twarde dowody)
- `captured_requests.json` - rzeczywiste requesty HTTP
- `*.log` z timestampami - logi wykonania
- `*.json` z wynikami testów - pomiary

### Ranga 2: **WYSOKA** (analiza istniejących danych)
- Reverse engineering kodu JS
- Analiza HAR files
- Porównanie z logami

### Ranga 3: **ŚREDNIA** (eksperckie oceny)
- Analiza konkurencji
- Ocena biznesowa
- Estymacje czasów

### Ranga 4: **NISKA** (hipotezy)
- AI-generated research
- Spekulacje bez dowodów
- Marketingowe deklaracje

## 🛠️ **NARZĘDZIA**

### 1. **manage_documentation_conflicts.py**
```bash
# Wygeneruj raport konfliktów
python manage_documentation_conflicts.py --report --output konflikty_raport.md

# Zaktualizuj syntezy (ręczna weryfikacja wymagana)
python manage_documentation_conflicts.py --update
```

### 2. **Manualne sprawdzenie:**
```bash
# Sprawdź czy dokumenty są spójne
grep -r "100% zweryfikowane" raporty/ --include="*.md"

# Sprawdź captured_requests dla dowodów
grep -i "checkout" vinted/dane/captured_requests.json

# Porównaj logi testów
diff vinted/testy_camoufox/docs/logs/bench_out.txt vinted/testy_camoufox/docs/logs/bench_opt_out.txt
```

## 📊 **STATUS SYSTEMU**

### ✅ **DZIAŁA:**
- Struktura syntez gotowa
- Narzędzie do znajdowania konfliktów
- Rejestr konfliktów (`00_POWTORZENIA...`)

### 🚧 **DO ZROBIENIA:**
- Automatyczne porównywanie captured_requests z dokumentami
- Integracja z CI/CD dla sprawdzania spójności
- Dashboard statusu konfliktów

### 🎯 **CELE:**
1. **0 niespójnych dokumentów** - jedna wersja prawdy
2. **Automatyczne wykrywanie** nowych konfliktów
3. **Przejrzystość** - wiadomo skąd pochodzą informacje

## 📞 **ODPOWIEDZIALNOŚCI**

### **Autor dokumentu:**
- Oznacza poziom pewności ([UDOWODNIONE]/[HIPOTEZA])
- Podaje źródła danych (captured_requests, logi, etc.)
- Aktualizuje przy nowych dowodach

### **Audytor:**
- Sprawdza spójność z istniejącymi danymi
- Oznacza konflikty w `00_POWTORZENIA...`
- Aktualizuje syntezy po rozstrzygnięciu

### **Developer:**
- Dostarcza nowe dane (testy, logs, captured_requests)
- Aktualizuje dokumentację przy zmianach w kodzie
- Używa systemu do utrzymania spójności

---

**Ostatnia aktualizacja systemu:** 2026-08-31  
**Status:** **W DRODZE** - struktura gotowa, wymaga adopcji  
**Kontakt:** Dokumentacja -> Syntezy -> Aktualna prawda