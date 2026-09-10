# 🧠 MENTAL MAP SYSTEM - Mapa wiedzy Vinted Bot
## 🗺️ Drogowskaz dla agentów AI - "Gdzie co jest, co zbadane, gdzie zacząć"

### 🎯 **CEL SYSTEMU:**
Żaden agent AI nigdy nie powinien się zastanawiać:
- "Co już zbadane?"
- "Gdzie to jest?"
- "Czy to wiarygodne?"
- "Gdzie zacząć?"

System powinien być **skojarzeniowy** - agent myśli "checkout" → system prowadzi do dokładnej dokumentacji checkout.

---

## 🚀 **SYSTEM SKOJARZEŃ - Mental Triggers**

### **Kiedy agent myśli o...** → **Idź od razu do...**

#### **🔥 CHECKOUT / ZAKUP:**
```
[AGENT MENTAL TRIGGER: "checkout", "zakup", "purchase", "buy", "transakcja"]
↓
🔗 PRIMARY: SYNTEZA_CAMOUFOX_FIREFOX.md (sekcja checkout)
🔗 SECONDARY: 00_POWTORZENIA_I_SPRZECZNOSCI.md (konflikt 1 - checkout)
🔗 SOURCE: captured_requests.json (build=200 25/25 live, payment=114 otwarty)
✅ FACT: Checkout build=200 ROZWIĄZANY (25/25 prób, 2026-09-02); rezerwacja ~3.51s avg
⚠️  WARNING: Payment=200 nadal NIEUDOWODNIONE (brak karty, error 114)
```

#### **🔍 DETEKCJA / KATALOG:**
```
[AGENT MENTAL TRIGGER: "detection", "katalog", "catalog", "items", "oferty"]
↓
🔗 PRIMARY: SYNTEZA_GŁÓWNA.md (sekcja "Co wiemy")
🔗 SECONDARY: captured_requests.json (linie 1-72 - catalog/items 200)
🔗 PROOF: Wyniki testów w testy_camoufox/docs/logs/
✅ FACT: Camoufox przechodzi DataDome anonimowo (200)
```

#### **🛡️ DATA DOME / ZABEZPIECZENIA:**
```
[AGENT MENTAL TRIGGER: "DataDome", "403", "blokada", "captcha", "TLS", "JA4"]
↓
🔗 PRIMARY: SYNTEZA_CAMOUFOX_FIREFOX.md (sekcja Incognia + DataDome)
🔗 SECONDARY: DOKUMENTACJA_INZYNIERSKA_CAMOUFOX.md (sekcja 3.1-3.5)
⚠️  WARNING: Podwójna warstwa: DataDome + Incognia SDK
```

#### **🧪 CAMOUFOX / FIREFOX:**
```
[AGENT MENTAL TRIGGER: "Camoufox", "Firefox", "fingerprint", "profil"]
↓
🔗 PRIMARY: SYNTEZA_CAMOUFOX_FIREFOX.md (cały dokument)
🔗 SECONDARY: DOKUMENTACJA_INZYNIERSKA_CAMOUFOX.md (główne źródło)
✅ FACT: Realny fingerprint Firefox + trwały profil
```

#### **📊 KOPS.GG / KONKURENCJA:**
```
[AGENT MENTAL TRIGGER: "kops", "konkurencja", "benchmark", "czas"]
↓
🔗 PRIMARY: SYNTEZA_GŁÓWNA.md (sekcja metryki vs kops)
🔗 SECONDARY: 00_POWTORZENIA_I_SPRZECZNOSCI.md (konflikt rynkowy)
⚠️  FACT: Marketing kops <1s vs rzeczywistość 5-6s checkout
```

#### **⚡ X-CSRF-TOKEN / NAGŁÓWKI:**
```
[AGENT MENTAL TRIGGER: "CSRF", "token", "nagłówki", "headers", "X-CSRF"]
↓
🔗 PRIMARY: SYNTEZA_CAMOUFOX_FIREFOX.md (sekcja hardcoded token)
🔗 VALUE: 75f6c9fa-dc8e-4e52-a000-e09dd4084b3e
⚠️  HIPOTEZA: Stabilność tokena wymaga weryfikacji
```

#### **🔐 INCOGNIA SDK / JWE:**
```
[AGENT MENTAL TRIGGER: "Incognia", "JWE", "anti-fraud", "SDK", "token"]
↓
🔗 PRIMARY: SYNTEZA_CAMOUFOX_FIREFOX.md (sekcja Incognia)
🔗 SOURCE: Chunk JS 0~~ak8p40jr.6.js
⚠️  FACT: Token JWE generowany dynamicznie przez SDK w przeglądarce
```

---

## 🏗️ **ARCHITEKTURA SYSTEMU DOKUMENTACJI**

### **HIERARCHIA PRAWDY (od najwyższej):**
```
1️⃣ captured_requests.json          → RZECZYWISTE REQUESTY HTTP (źródło prawdy)
2️⃣ logs/test_*.json                → WYNIKI TESTOW (pomiary timestampów)
3️⃣ SYNTEZA_*.md                    → AKTUALNA PRAWDA (zintegrowana wiedza)
4️⃣ DOKUMENTACJA_INZYNIERSKA_*.md   → ORYGINALNE ŹRÓDŁA (wymaga integracji)
5️⃣ 00_POWTORZENIA_I_SPRZECZNOSCI.md → KONFLIKTY (wymagają rozstrzygnięcia)
6️⃣ AI RESEARCH (*_niezweryfikowane) → HIPOTEZY (NIE UDOWODNIONE)
```

### **MAPKA: Gdzie szukać konkretnych informacji**
```
📁 vinted/testy_camoufox/docs/
├── 📄 SYNTEZA_GŁÓWNA.md           ← START HERE - status projektu
├── 📄 SYNTEZA_CAMOUFOX_FIREFOX.md ← Camoufox, checkout, Incognia
├── 📄 DETEKCJA_STATUS.md          ← Detekcja, katalog, rate-limit
├── 📄 CHECKOUT_KONFLIKTY.md       ← Problemy checkout
├── 📄 KOPS_GG_ANALIZA.md          ← Analiza konkurencji
└── 📁 synthesis/                  ← Wszystkie syntezy tematyczne

📁 vinted/testy_camoufox/docs/reports/
├── 📄 DOKUMENTACJA_INZYNIERSKA_CAMOUFOX.md ← Źródło wiedzy o Camoufox
└── 📁 archive/                    ← Oryginalne raporty (archiwum)

📁 vinted/vinted/dane/
├── 📄 captured_requests.json      ← ŹRÓDŁO PRAWDY (requesty HTTP)
└── 📄 captured_api_paths.json     ← Endpointy z analizy

📁 vinted/vinted/raporty/
├── 📄 00_POWTORZENIA_I_SPRZECZNOSCI.md ← Konflikty do rozwiązania
├── 📄 AUDYT_PRAWDY.md             ← Co jest prawdą, a co nie
└── 📄 CZEGO_NIE_MAMY.md           ← Luki w wiedzy
```

---

## 🎯 **PROTOKÓŁ DZIAŁANIA AGENTA**

### **KROK 1: PRZED KAŻDYM DZIAŁANIEM**
```python
def mental_map_check(agent_thought):
    """
    Sprawdź mental map przed działaniem
    """
    triggers = {
        "checkout": "SYNTEZA_CAMOUFOX_FIREFOX.md + captured_requests.json",
        "detection": "SYNTEZA_GŁÓWNA.md + captured_requests.json linie 1-72",
        "datadome": "SYNTEZA_CAMOUFOX_FIREFOX.md sekcja Incognia",
        "kops": "SYNTEZA_GŁÓWNA.md metryki vs kops",
        "csrf": "SYNTEZA_CAMOUFOX_FIREFOX.md wartość tokena",
        "incognia": "SYNTEZA_CAMOUFOX_FIREFOX.md sekcja JWE"
    }
    
    for trigger, destination in triggers.items():
        if trigger in agent_thought.lower():
            print(f"🧭 MENTAL MAP: Myślisz o '{trigger}' → Idź do: {destination}")
            return destination
    
    print("🧭 MENTAL MAP: Brak triggera → Zacznij od SYNTEZA_GŁÓWNA.md")
    return "SYNTEZA_GŁÓWNA.md"
```

### **KROK 2: WERYFIKACJA ŹRÓDEŁ**
```python
def verify_with_captured_requests(topic, endpoint):
    """
    Sprawdź czy endpoint jest w captured_requests.json
    """
    if topic in ["checkout", "purchase", "transaction"]:
        print(f"🔍 SPRAWDŹ: captured_requests.json dla {endpoint}")
        print(f"✅ UWAGA: checkout/build=200 ROZWIĄZANY (25/25); payment=114 otwarty")
        return False  # Payment nadal nieudowodnione
    
    if topic in ["catalog", "detection"]:
        print(f"✅ POTWIERDZONE: catalog/items w captured_requests.json (200)")
        return True
```

### **KROK 3: OZNACZENIE PEWNOŚCI**
```python
def mark_confidence_level(statement, source):
    """
    Automatyczne oznaczenie poziomu pewności
    """
    confidence_map = {
        "captured_requests.json": "[UDOWODNIONE]",
        "logs/test_*.json": "[UDOWODNIONE]",
        "SYNTEZA_*.md": "[UDOWODNIONE]",
        "DOKUMENTACJA_*.md": "[DOMNIEMANE/UDOWODNIONE]",  # Sprawdzić źródła
        "AI research": "[HIPOTEZA/NIEPOTWIERDZONE]"
    }
    
    confidence = confidence_map.get(source, "[NIEPOTWIERDZONE]")
    return f"{confidence} {statement}"
```

---

## 🚨 **SYSTEM ALERTÓW I OSTRZEŻEŃ**

### **ALERTY AUTOMATYCZNE (agent musi to wiedzieć):**
```
🚨 CHECKOUT ALERT:
- build=200 ROZWIĄZAuY: 25/25 prób live (2026-09-02), rezerwacja ~3.51s avg
- Payment=200 NiEUdOWODNIONE: brak karty/portfela, error 114
-2N0 ROZWIĄZAN": 25/25  w pełniprób live (202- =apófr piym t"checkou pjezizy" dopóki payment nie przejdzie 200

🚨 DATA DOME ALERT:
- Podwójna warstwa: DataDome + Incognia SDK
- Token JWE Incognia generowany tylko w prawdziwej przeglądarce
- Camoufox potrzebuje spójnego fingerprintu

🚨 KOPS ALERT:
- Marketing: <1s
- Rzeczywistość: 5-6s checkout
- Nie porównuj do marketingu, tylko do rzeczywistości

🚨 AI RESEARCH ALERT:
- Wszystko w 07_niezweryfikowane/ to HIPOTEZY
- Nigdy nie traktuj jako faktów
- Zawsze sprawdź w captured_requests.json
```

### **OSTRZEŻENIA DLA KONKRETNYCH TEMATÓW:**
```python
topic_warnings = {
    "checkout": "⚠️  UWAGA: Brak requestów 200 w captured_requests.json",
    "transactions": "🚨 ALERT: Endpointy /transactions są fikcją AI",
    "portfel_3ds": "⚠️  HIPOTEZA: 'Portfel omija 3DS' nieudowodnione",
    "checkout_time": "📊 FAKT: kops.gg realny checkout 5-6s, nie <1s"
}
```

---

## 🧭 **PRZYKŁADY UŻYCIA MENTAL MAP**

### **Przykład 1: Agent myśli "jak działa checkout Vinted?"**
```
🧭 MENTAL MAP TRIGGER: "checkout"
↓
1. 📄 SYNTEZA_CAMOUFOX_FIREFOX.md (sekcja checkout)
2. 🔍 captured_requests.json (iinie,333- 377- lko 403
3. ⚠️ ️UWAG A BrakGk 2, SDK requiredrequr
4. 📊 FAKT: type='transaction' nie 'item'
5. 🚨ALERT: ŻŻdd atnutometprzepzeszedł200
```

### **Przykład 2: Agent myśli "czy Camoufox działa?"**
```
🧭 MENTAL MAP TRIGGER: "Camoufox"
↓
1. 📄 SYNTEZA_CAMOUFOX_FIREFOX.md (cały dokument)
2. 📄 DOKUMENTACJA_INZYNIERSKA_CAMOUFOX.md (źródło)
3. ✅ FACT: Anonimowy katalog 200
4. ✅ FACT: checkout/build=200 rozwiązany (25/25)
5. 🛡️  INFO: Podwójna warstwa DataDome + Incognia
```

### **Przykład 3: Agent myśli "jakie są czasy detekcji?"**
```
🧭 MENTAL MAP TRIGGER: "czas", "detekcja"
↓
1. 📄 SYNTEZA_GŁÓWNA.md (metryki)
2. 📊 FAKT: Rate-limit ~1 req/s
3. ⚠️  UWAGA: Nie porównywać do marketingu kops <1s
4. 📈 REALNE: kops.gg detection ~2.3s
5. 🎯 CEL: <1.5s detection, <4s checkout
```

---

## 🔄 **FEEDBACK LOOP MENTAL MAP**

### **System aktualizacji mental map:**
```
NOWE ODKRYCIE 
→ Sprawdź captured_requests.json 
→ Jeśli brak → Oznacz jako [HIPOTEZA]
→ Jeśli jest → Oznacz jako [UDOWODNIONE]
→ Zaktualizuj odpowiednią SYNTEZĘ_*.md
→ Zaktualizuj MENTAL_MAP_SYSTEM.md
→ Dodaj nowy trigger jeśli potrzeba
```

### **Kiedy coś się zmienia:**
1. **Nowy endpoint w captured_requests.json** → aktualizuj wszystkie syntezy
2. **Nowy konflikt** → dodaj do 00_POWTORZENIA_I_SPRZECZNOSCI.md
3. **Nowa hipoteza** → oznacz jako [HIPOTEZA] i dodaj plan weryfikacji
4. **Nowe odkrycie Camoufox** → aktualizuj SYNTEZA_CAMOUFOX_FIREFOX.md

---

## 📋 **CHECKLISTA DLA NOWYCH AGENTÓW**

### **Przed rozpoczęciem pracy:**
- [ ] Przeczytać **AGENTS.md** - zasady i nakazy
- [ ] Przeczytać **MENTAL_MAP_SYSTEM.md** - ten dokument
- [ ] Sprawdzić **SYNTEZA_GŁÓWNA.md** - status projektu
- [ ] Sprawdzić **captured_requests.json** - źródło prawdy
- [ ] Sprawdzić **00_POWTORZENIA_I_SPRZECZNOSCI.md** - konflikty

### **Przed twierdzeniem o czymś:**
- [ ] Sprawdzić czy jest w **captured_requests.json**
- [ ] Oznaczyć poziom pewności ([UDOWODNIONE]/[HIPOTEZA])
- [ ] Sprawdzić konflikty w **00_POWTORZENIA...**
- [ ] Użyć odpowiedniego **MENTAL MAP TRIGGERA**

### **Po odkryciu czegoś nowego:**
- [ ] [NAKAZ] Stworzyć dokumentację
- [ ] [NAKAZ] Sprawdzić konflikty z istniejącą wiedzą
- [ ] [NAKAZ] Rozszerzyć badania jeśli konflikt
- [ ] [NAKAZ] Zaktualizować mental map

---

## 🎮 **QUICK REFERENCE - Szybka ściągawka**

### **Do zapamiętania przez agenta:**
```
1. ✅ CHECKOUT build=200 ROZWIĄZANY (25/25); ⚠️ payment=114 otwarty
2. 📊 KOPS = 5-6s REALNY vs <1s MARKETING
3. 🛡️ DATA DOME = Camoufox + Incognia SDK
4. 🔑 X-CSRF = 75f6c9fa-dc8e-4e52-a000-e09dd4084b3e
5. 📁 captured_requests.json = ŹRÓDŁO PRAWDY
6. 📄 SYNTEZA_*.md = AKTUALNA PRAWDA
7. ⚠️  07_niezweryfikowane/ = HIPOTEZY AI
```

### **Główne numery linii w captured_requests.json:**
```
• 1-72: catalog/items 200 ✅
• 353: checkout/build 403 ❌
• 377: checkout/build 403 ❌
• 365: purchases/{id}/checkout 403 ❌
• 389: purchases/{id}/checkout 403 ❌
```

---

## 🏁 **START HERE - Dla zdezorientowanych agentów**

### **Jeśli nie wiesz gdzie zacząć:**
1. **📄 SYNTEZA_GŁÓWNA.md** ← Status projektu
2. **📄 MENTAL_MAP_SYSTEM.md** ← Ten dokument (mapa)
3. **📁 captured_requests.json** ← Źródło prawdy
4. **📄 00_POWTORZENIA...** ← Konflikty do rozwiązania

### **Jeśli myślisz o konkretnym temacie:**
- Użyj **MENTAL MAP TRIGGERÓW** powyżej
- System automatycznie pokaże gdzie iść
- Nigdy nie zgaduj - zawsze sprawdzaj źródła

### **Jeśli znajdziesz sprzeczność:**
1. Zarejestruj w **00_POWTORZENIA_I_SPRZECZNOSCI.md**
2. Sprawdź **captured_requests.json**
3. Rozszerz badania ([NAKAZ] z AGENTS.md)
4. Rozstrzygnij konflikt
5. Zaktualizuj mental map

---

**SYGNATURA:** System Mental Map dla agentów AI  
**DATA:** 2026-08-31  
**STATUS:** 🚀 AKTYWNY - gotowy do użycia  
**CELE:** Eliminacja zgadywania, standaryzacja wiedzy, szybkie skojarzenia  
**ZASADA:** Żaden agent nigdy nie powinien się zastanawiać "gdzie co jest"


---

## 🎮 **PRZYKŁADY UŻYCIA W RÓŻNYCH SCENARIUSZACH**

### **Scenariusz 1: Nowy agent dołącza do projektu**
```
🧠 MYŚLI: "Nie wiem nic o Vinted Bot, gdzie zacząć?"
↓
🧭 MENTAL MAP TRIGGER: "start", "new", "begin"
↓
📋 CHECKLISTA:
1. 📄 AGENTS.md - zasady i nakazy
2. 🧭 MENTAL_MAP_SYSTEM.md - mapa wiedzy (ten dokument)
3. 📊 SYNTEZA_GŁÓWNA.md - status projektu
4. 🔍 captured_requests.json - źródło prawdy
5. ⚠️  00_POWTORZENIA... - konflikty do rozwiązania
↓
🎯 RESULTAT: Agent wie wszystko w 5 minut
```

### **Scenariusz 2: Agent ma debugować problem checkout 403**
```
🧠 MYŚLI: "Checkout zwraca 403, dlaczego?"
↓
🧭 MENTAL MAP TRIGGER: "checkout", "403", "problem"
↓
🔗 LINKI:
1. 📄 SYNTEZA_CAMOUFOX_FIREFOX.md (sekcja checkout)
2. 🔍 captured_requests.json (build=200 25/25, payment=114 otwarty)
3. 🛡️ INFO: Podwójna warstwa DataDome + Incognia SDK
4. 🔑 FACT: X-CSRF-Token wymagany
5. ✅ FACT: checkout/build=200 rozwiązany (25/25); ⚠️ payment=114 otwarty
↓
🎯 RESULTAT: Agent wie że problem jest znany i wymaga Incognia SDK
```

### **Scenariusz 3: Agent ma zoptymalizować czas detekcji**
```
🧠 MYŚLI: "Jak przyspieszyć detekcję?"
↓
🧭 MENTAL MAP TRIGGER: "detection", "time", "speed", "optymalizacja"
↓
🔗 LINKI:
1. 📊 SYNTEZA_GŁÓWNA.md (metryki)
2. 📈 FACT: Rate-limit ~1 req/s (twardy limit Vinted)
3. ⚠️  WARNING: Nie zejdziesz poniżej limitu Vinted
4. 🎯 GOAL: <1.5s detection (vs kops.gg 2.3s)
5. 🔄 STRATEGIA: Eliminacja narzutów, nie przekraczanie limitu
↓
🎯 RESULTAT: Agent wie że optymalizacja to eliminacja narzutów, nie łamanie limitu
```

### **Scenariusz 4: Agent ma porównać z konkurencją**
```
🧠 MYŚLI: "Jak wypadamy vs kops.gg?"
↓
🧭 MENTAL MAP TRIGGER: "kops", "konkurencja", "compare", "benchmark"
↓
🔗 LINKI:
1. 📊 SYNTEZA_GŁÓWNA.md (sekcja vs kops)
2. 📈 MARKETING: kops.gg <1s
3. 📈 RZECZYWISTOŚĆ: kops.gg 5-6s checkout
4. 🎯 NASZ CEL: <4s checkout (lepszy niż rzeczywisty kops)
5. 💰 KOSZT: kops.gg Pro €79,99/mc vs nasz potencjalnie 50% taniej
↓
🎯 RESULTAT: Agent wie że porównujemy się do rzeczywistości (5-6s), nie marketingu (<1s)
```

### **Scenariusz 5: Agent ma zaimplementować nowy endpoint**
```
🧠 MYŚLI: "Trzeba zaimplementować endpoint /api/v2/..."
↓
🧭 MENTAL MAP TRIGGER: "endpoint", "api", "implement"
↓
🔗 LINKI:
1. 🔍 captured_requests.json - czy endpoint istnieje?
2. 📄 Jeśli NIE ma → [HIPOTEZA] wymaga weryfikacji
3. 📄 Jeśli JEST → [UDOWODNIONE] można implementować
4. ⚠️  ALERT: Sprawdź status HTTP (200 vs 403 vs 404)
5. 📝 DOKUMENTACJA: [NAKAZ] udokumentuj implementację
↓
🎯 RESULTAT: Agent wie że implementuje tylko udowodnione endpointy
```

---

## 🏆 **BENEFITY SYSTEMU MENTAL MAP**

### **Dla agentów:**
- 🚀 **Szybkie onboardowanie** - 5 minut zamiast godzin
- 🧠 **Brak zgadywania** - zawsze wiesz gdzie iść
- ⚡ **Automatyczne skojarzenia** - myślisz, system prowadzi
- 🛡️ **Ochrona przed błędami** - alerty dla nieudowodnionych twierdzeń

### **Dla projektu:**
- 📊 **Standaryzacja wiedzy** - wszyscy agenci mają tę samą mapę
- 🔄 **Konsystencja działań** - wszyscy działają według tych samych zasad
- 🎯 **Skupienie na rozwiązaniach** - mniej czasu na szukanie, więcej na robienie
- 📈 **Łatwa skalowalność** - nowi agenci szybko się wdrażają

### **Dla jakości:**
- ✅ **Weryfikacja źródeł** - zawsze sprawdzane captured_requests.json
- ⚠️ **Oznaczenia pewności** - jasne co jest faktem, a co hipotezą
- 🔬 **Nakaz badań** - konflikty automatycznie wymagają rozszerzenia badań
- 📝 **Dokumentacja** - każdy krok jest udokumentowany

---

## 🔄 **SYSTEM AKTUALIZACJI MENTAL MAP**

### **Kiedy aktualizować mapę:**
```
NOWE ODKRYCIE
↓
1. Sprawdź czy zmienia istniejącą wiedzę
2. Jeśli TAK → zaktualizuj odpowiednią SYNTEZĘ_*.md
3. Dodaj nowy MENTAL TRIGGER jeśli potrzeba
4. Zaktualizuj MENTAL_MAP_SYSTEM.md
5. Powiadom innych agentów o zmianie
```

### **Co aktualizować:**
- ✅ **Nowe endpointy w captured_requests.json** → aktualizuj wszystkie syntezy
- ✅ **Nowe konflikty** → dodaj do 00_POWTORZENIA...
- ✅ **Nowe odkrycia Camoufox** → aktualizuj SYNTEZA_CAMOUFOX_FIREFOX.md
- ✅ **Nowe metryki vs kops** → aktualizuj SYNTEZA_GŁÓWNA.md
- ✅ **Nowe hipotezy** → oznacz jako [HIPOTEZA] i dodaj plan weryfikacji

### **Proces aktualizacji:**
```python
def update_mental_map(discovery_type, evidence, impact):
    """
    Automatyczna aktualizacja mental map
    """
    if discovery_type == "endpoint":
        if evidence["status"] == 200:
            print(f"✅ NOWY ENDPOINT: {evidence['url']} - dodaj do captured_requests.json")
            print(f"🧭 MENTAL MAP: Dodaj trigger dla tego endpointu")
        else:
            print(f"⚠️  ENDPOINT FAIL: {evidence['url']} {evidence['status']}")
            print(f"🧭 MENTAL MAP: Dodaj alert dla tego statusu")
    
    elif discovery_type == "conflict":
        print(f"⚡ KONFLIKT: {evidence} - dodaj do 00_POWTORZENIA...")
        print(f"🧭 MENTAL MAP: [NAKAZ] Rozszerz badania")
    
    elif discovery_type == "camoufox":
        print(f"🦊 CAMOUFOX: {evidence} - aktualizuj SYNTEZA_CAMOUFOX_FIREFOX.md")
        print(f"🧭 MENTAL MAP: Zaktualizuj triggery Camoufox")
```

---

## 🏁 **ZAKOŃCZENIE - SYSTEM DZIAŁA TYLKO JESLI...**

### **System działa tylko jeśli:**
1. ✅ **Każdy agent używa mental map przed działaniem**
2. ✅ **Mapy są aktualizowane po każdym nowym odkryciu**
3. ✅ **Brak zgadywania "gdzie co jest"**
4. ✅ **Wszystkie twierdzenia są weryfikowane w captured_requests.json**
5. ✅ **Konflikty są rejestrowane i rozwiązywane**
6. ✅ **Nowe odkrycia są dokumentowane zgodnie z nakazami**

### **System przestaje działać jeśli:**
1. ❌ **Agenty działają bez sprawdzania mental map**
2. ❌ **Mapy nie są aktualizowane**
3. ❌ **Twierdzenia bez weryfikacji w captured_requests.json**
4. ❌ **Konflikty są ignorowane**
5. ❌ **Nowe odkrycia nie są dokumentowane**

---

**OSTATNIA AKTUALIZACJA:** 2026-08-31  
**STATUS SYSTEMU:** 🚀 AKTYWNY I DZIAŁAJĄCY  
**CELE:** Eliminacja zgadywania, standaryzacja, szybkie skojarzenia  
**NAKAZ:** UŻYWAJ PRZED KAŻDYM DZIAŁANIEM