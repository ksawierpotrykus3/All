# ROZSTRZYGNIĘCIE KONFLIKTU PRZEDMIOTÓW TESTOWYCH
## [DATA] 2026-08-31 - [AKCJA] Konsolidacja danych testowych

### 🔍 **KONFLIKT IDENTYFIKOWANY:**
**SPRZECZNOŚĆ 3 z 00_POWTORZENIA_I_SPRZECZNOSCI.md**

- **Źródło 1:** `02_reverse_engineering/` - przedmiot 9784711276 (koszulka FSBN)
- **Źródło 2:** `03_weryfikacja/` - przedmiot 9782578256 (zimowa kurtka Bershka)
- **Źródło 3:** `bot/diag_checkout.py` - przedmiot 9807925466
- **Problem:** 3 różne przedmioty testowe, brak standaryzacji

### 📊 **DANE Z ANALIZY:**
```python
# ZIDENTYFIKOWANE PRZEDMIOTY TESTOWE:
test_items = {
    "reverse_engineering": {
        "item_id": 9784711276,
        "opis": "Koszulka FSBN",
        "cena": "10 PLN",
        "folder": "02_reverse_engineering/"
    },
    "weryfikacja": {
        "item_id": 9782578256, 
        "opis": "Zimowa kurtka Bershka",
        "cena": "?",
        "folder": "03_weryfikacja/"
    },
    "bot_tests": {
        "item_id": 9807925466,
        "opis": "Nieznany",
        "cena": "?",
        "folder": "bot/diag_checkout.py"
    }
}
```

### 🎯 **WNIOSKI [UDOWODNIONE]:**
1. ✅ **3 różne przedmioty testowe** używane w różnych częściach projektu
2. ✅ **Brak standaryzacji** - każdy test używa innych danych
3. ✅ **Konto docelowe:** `konto_A` (id 111111111) - potwierdzone
4. ✅ **konto_B wykluczone** - zgodność wszystkich źródeł

### 🔬 **[NAKAZ] STANDARYZACJA TESTOW (wymagane):**
**Problem:** Brak spójnych danych testowych utrudnia reprodukcję i analizę

**Wymagane działania:**
1. **Definicja standardowych danych testowych**
2. **Konsolidacja wszystkich testów** do jednego zestawu danych
3. **Dokumentacja** procedur testowych

**Proponowany standard testowy:**
```python
# STANDARD TESTOWY VINTED BOT:
STANDARD_TEST_CONFIG = {
    "account": {
        "id": "konto_A",
        "user_id": 111111111,
        "status": "active"
    },
    "test_item": {
        "id": 9807925466,  # lub wybrany standardowy
        "category": "odzież",
        "price_range": "10-50 PLN",
        "availability": "dostępny"
    },
    "test_procedures": {
        "detection": "API catalog/items",
        "checkout": "Próba zakupu",
        "validation": "Sprawdzenie captured_requests.json"
    }
}
```

### 📝 **DOKUMENTACJA STANDARYZACJI:**
**Nowe pliki do stworzenia:**
1. `vinted/testy_camoufox/docs/STANDARD_TEST_CONFIG.md` - konfiguracja testów
2. `vinted/testy_camoufox/tools/test_data_manager.py` - zarządzanie danymi testowymi
3. Aktualizacja istniejących testów do standardu

### 📅 **NEXT STEPS:**
1. **Dziś:** Wybór standardowego przedmiotu testowego
2. **Jutro:** Aktualizacja wszystkich testów do standardu
3. **Pojutrze:** Dokumentacja procedur testowych

### 🏆 **REKOMENDOWANY STANDARD:**
**Przedmiot testowy:** `9807925466` (używany w bot/diag_checkout.py)
**Powód:** Najnowszy, używany w aktywnych testach, dostępny w logach

**Konto testowe:** `konto_A` (id 111111111)
**Powód:** Potwierdzone przez wszystkie źródła, konto_B wykluczone

---

**SYGNATURA:** Agent AI - konsolidacja danych testowych  
**DATA ROZSTRZYGNIĘCIA:** 2026-08-31  
**STATUS:** Konflikt ROZSTRZYGNIĘTY - wymagana standaryzacja  
**AKCJA:** Stworzenie standardowej konfiguracji testowej