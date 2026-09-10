# Design: Enhanced Vinted Bot - Spełnienie wymagań z rozmowa_smartcare.md

## 📊 **STATUS PROJEKTU - ANALIZA BAZOWA**

### ✅ **[UDOWODNIONE] Co wiemy:**
- Endpoint `/api/v2/catalog/items` działa (captured_requests.json linie 1-72)
- Rate-limit Vinted ~1 req/s potwierdzony (testy stabilności)
- Fingerprint Firefox 152 przechodzi detekcję (HTTP 200 z danymi)
- CSRF token `75f6c9fa-dc8e-4e52-a000-e09dd4084b3e` hardcoded w JS
- Filtry: brand, size, status, price, search_text działają w API

### ❌ **[HIPOTEZA] Co nie wiemy:**
- Checkout endpointy nie przechwycone (brak w captured_requests.json)
- DataDome 403 blokuje checkout/build mimo poprawnych tokenów
- Rzeczywisty czas checkoutu niezmierzony (nigdy nie kupiliśmy)
- Przepływ płatności niezweryfikowany

### ⚠️ **[KONFLIKT] Sprzeczności:**
- AI research mówi "100% zweryfikowany checkout" vs brak dowodów w capture
- Marketing kops.gg "<1s" vs rzeczywistość "2.3s detection + 5-6s checkout"

## 🎯 **WYMAGANIA KLIENTA (rozmowa_smartcare.md)**

### 1. **Ultra-wysoka prędkość**
- Cel: Pokonać kops.gg (<1s detection, <4s checkout)
- Rzeczywistość kops: 2.3s detection + 5-6s checkout
- Nasz cel realistyczny: ~1.5s detection + ~4s checkout

### 2. **Architektura serwerowa (brak Discorda)**
- VPS/dedykowany serwer
- Panel webowy lub CLI do zarządzania
- **Wybór: CLI jako główny interfejs**

### 3. **Zaawansowane filtry**
- Marka, stan, przedział cenowy, słowa kluczowe, kategorie, rozmiary
- **Status: Część działa w API, kategorie wymagają post-processingu**

### 4. **Multikonto Autocop (3-4 konta)**
- Jednoczesne monitorowanie i kupowanie
- **Wybór: Pełna izolacja kont (fingerprint, proxy, cookies)**

### 5. **Ochrona przed banami**
- Residential proxy rotacyjne
- Fingerprint spoofing przeglądarki/systemu
- Losowe, human-like opóźnienia
- Realistyczne oczekiwania: bany będą, ale rzadziej

### 6. **Pomiary rzeczywistej prędkości**
- Transparentne benchmarki vs kops.gg
- **Wybór: Realistyczne metryki, nie marketing hype**

## 🏗️ **ARCHITEKTURA SYSTEMU**

### **Enhanced curl_cffi z pełną izolacją kont**
```
MASTER PROCESS (CLI Orchestrator)
├── ACCOUNT WORKER 1 (pełna izolacja)
│   ├── Fingerprint: Firefox 152 + custom extensions
│   ├── Proxy: Residential pool (rotacyjne)
│   ├── Cookies: Własny plik, refresh token
│   └── Config: Własne filtry, timingi
├── ACCOUNT WORKER 2 (identyczna izolacja)
├── ACCOUNT WORKER 3 (identyczna izolacja)
└── ACCOUNT WORKER 4 (identyczna izolacja)
```

### **SHARED SERVICES**
- **Proxy Manager** - rotacja, health check, koszt monitoring
- **Evidence Collector** - zapis dowodów, timingi, screenshots
- **Alert System** - powiadomienia (email, webhook)
- **Config Manager** - YAML/JSON zarządzanie konfiguracją

## 🔧 **MODUŁY TECHNICZNE**

### **1. Enhanced Fingerprint Module**
```python
# Problem: Obecny fingerprint FF152 działa dla detekcji, ale checkout 403
# Rozwiązanie: Pełny fingerprint przeglądarki + dodatkowe nagłówki

class EnhancedFingerprint:
    def get_session_kwargs(self) -> dict:
        return {
            "impersonate": "firefox152",
            "ja3": FF152_JA3,
            "akamai": FF152_AKAMAI,
            "extra_fp": self._get_full_tls_extensions(),
            "headers": self._get_enhanced_headers()  # Dodaje brakujące nagłówki przeglądarki
        }
```

### **2. Residential Proxy Manager**
```python
# Problem: Brak obsługi proxy rezydencjalnych
# Rozwiązanie: Modularny manager z health check i rotacją

class ResidentialProxyManager:
    def rotate_proxy(self, account_id: str) -> dict:
        """Rotuje proxy z uwzględnieniem geolokalizacji i limitów"""
        proxy = self._select_optimal_proxy(account_id)
        return self._format_proxy_url(proxy)
    
    def _health_check(self, proxy: dict) -> bool:
        """Testuje proxy na Vinted API"""
        return response.status_code == 200  # HTTP 200 = proxy działa
```

### **3. Account Worker z Full Isolation**
```python
# Problem: Daemon ma podstawową wielokontowość, brak pełnej izolacji
# Rozwiązanie: Każde konto jako osobny proces z własną konfiguracją

class AccountWorker(multiprocessing.Process):
    def __init__(self, account_config_path: str):
        self.config = self._load_yaml_config(account_config_path)
        self.fingerprint = EnhancedFingerprint(self.config["fingerprint_profile"])
        self.proxy = self.proxy_manager.rotate_proxy(self.config["account_id"])
        self.session = self._create_isolated_session()
```

### **4. Extended CLI z Config Management**
```python
# Problem: Obecny CLI ma podstawowe funkcje
# Rozwiązanie: Rozbudowany CLI z YAML/JSON configs

@click.group()
def vinted():
    """Vinted Bot Pro - zarządzanie wieloma kontami"""

@vinted.command()
@click.option('--accounts', multiple=True)
@click.option('--config-dir', default='./config')
def start(accounts, config_dir):
    """Uruchamia bot na wybranych kontach"""
    workers = []
    for account_name in accounts:
        worker = AccountWorker(f'{config_dir}/accounts/{account_name}.yaml')
        worker.start()
        workers.append(worker)
```

### **5. Benchmark Collector z Realistic Metrics**
```python
# Problem: Brak rzeczywistych pomiarów checkoutu vs kops.gg
# Rozwiązanie: Systematyczne zbieranie timingów i porównanie

class BenchmarkCollector:
    def generate_report(self) -> dict:
        return {
            "comparison_vs_kops": {
                "kops_marketing_detection": "<1s",
                "our_actual_detection": f"{self.timings['detection_avg']:.1f}s",
                "kops_real_checkout": "5-6s (potwierdzone przez klienta)",
                "our_actual_checkout": f"{self.timings['checkout_avg']:.1f}s",
                "conclusion": "Realistic vs marketing hype"
            }
        }
```

### **6. Checkout Experiment Module**
```python
# Problem: DataDome 403 blokuje checkout mimo poprawnych tokenów
# Rozwiązanie: Systematyczne testowanie różnych kombinacji

class CheckoutExperiment:
    def _generate_test_cases(self) -> list:
        return [
            {"name": "full_firefox_fingerprint", "fingerprint": "firefox152_full"},
            {"name": "enhanced_csrf_anon", "headers": "enhanced_auth"},
            {"name": "incognia_jwe_full", "incognia": "full_jwe_token"}
        ]
    
    def run_experiments(self, test_item_id: int):
        """Testuje różne kombinacje bypassu DataDome"""
        for test_case in self.test_cases:
            result = self._test_checkout(test_item_id, test_case)
            if result["status_code"] != 403:
                self._capture_successful_request(result)  # Zapis do captured_requests.json
```

## 📅 **ROADMAP IMPLEMENTACJI**

### **FAZA 1: Stabilizacja i pomiary (2 tygodnie)**
1. Enhanced fingerprint - rozszerzenie curl_cffi
2. Checkout experiments - systematyczne testowanie bypassu DataDome
3. Real benchmarks - pomiary na testowych przedmiotach

### **FAZA 2: Multikonto i proxy (3 tygodnie)**
1. Residential proxy integration - manager z rotacją
2. Full account isolation - worker processes
3. Extended CLI - zarządzanie YAML configs

### **FAZA 3: Production ready (2 tygodnie)**
1. Evidence system - automatyczne zbieranie dowodów
2. Alert system - powiadomienia
3. Deployment scripts - automatyzacja VPS

## 📈 **OCZEKIWANE REZULTATY**

### **Przewaga nad kops.gg:**
- **Szybsza detekcja**: ~1.5s (vs kops 2.3s) - 35% szybsze
- **Szybszy checkout**: ~4s (vs kops 5-6s) - 25-33% szybsze
- **Niższe koszty**: 50% niższy niż kops Pro plan (€79,99/mc)
- **Pełna kontrola**: Custom fingerprint, własne proxy, izolacja
- **Przezroczystość**: Rzeczywiste metryki, nie marketing hype

### **Success Criteria:**
- Detection time: <2s (cel: 1.5s)
- Checkout time: <5s (cel: 4s) 
- Success rate: >90% po rozwiązaniu DataDome 403
- Cost: 50% niższy niż kops.gg
- Konta: 3-4 jednocześnie z pełną izolacją

## 🚨 **RYZYKA I MITIGACJA**

### **Ryzyko 1: DataDome nie do pokonania curl_cffi**
- **Mitigacja**: Fallback do Camoufox/Playwright dla checkoutu
- **Plan B**: Hybrid approach - detekcja przez curl_cffi, checkout przez przeglądarkę

### **Ryzyko 2: Bany kont mimo izolacji**
- **Mitigacja**: Pełna izolacja fingerprint + proxy, realistic delays
- **Monitoring**: Early detection ban patterns, adaptive strategies

### **Ryzyko 3: Koszty proxy rezydencjalnych**
- **Mitigacja**: Optymalizacja rotacji, shared pool, koszt monitoring
- **Transparency**: Clear cost breakdown dla klienta

## 🔗 **INTEGRACJA Z SYSTEMEM DOKUMENTACJI**

### **Zgodność z AGENTS.md:**
- ✅ **[NAKAZ] Sprawdzanie captured_requests.json przed twierdzeniami**
- ✅ **[NAKAZ] Oznaczanie poziomu pewności ([UDOWODNIONE]/[HIPOTEZA])**
- ✅ **[NAKAZ] Tworzenie dokumentacji dla nowych odkryć**
- ✅ **[NAKAZ] Konfrontacja z istniejącą dokumentacją**
- ✅ **[NAKAZ] Rozszerzanie badań przy konfliktach**

### **Aktualizacja dokumentacji:**
1. **Nowe captured_requests** z udanych testów checkout → append do JSON
2. **Updated syntezy** w `testy_camoufox/docs/synthesis/`
3. **Rozstrzygnięcie konfliktów** w `00_POWTORZENIA_I_SPRZECZNOSCI.md`
4. **Nowe raporty benchmarków** w `docs/superpowers/plans/`

## 🏁 **WNIOSKI**

### **Bot idzie w DOBRYM KIERUNKU:**
1. **Solidne podstawy badawcze** - captured_requests.json, analiza JS, testy fingerprint
2. **Modularna architektura** - łatwa do rozszerzenia (curl_cffi, Click, multiprocessing)
3. **Realistyczne podejście** - uczciwe benchmarki vs marketing hype kops.gg

### **Kluczowe wyzwanie:**
- **DataDome 403 na checkout** - wymaga systematycznych eksperymentów
- **Brak przechwyconego checkout flow** - konieczne nowe testy z Camoufox

### **Rekomendacja:**
**Enhanced curl_cffi z pełną izolacją kont** to optymalna ścieżka rozwoju, która spełni wszystkie wymagania klienta z zachowaniem realizmu technicznego i biznesowego.

---

**Data:** 2026-08-31  
**Autor:** Analiza zgodna z AGENTS.md  
**Status designu:** ✅ ZATWIERDZONY przez użytkownika  
**Następny krok:** Invoke writing-plans skill dla implementation plan