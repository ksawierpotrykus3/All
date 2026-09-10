# Architektura: "Zajeb z przeglądarki tylko to co najlepsze"

**Data:** 2026-08-30
**Status:** Propozycja architektoniczna — wyciągnięcie z przeglądarki tylko fingerprintu DataDome

---

## 1. Koncept

**"Zajeb z przeglądarki tylko to co najlepsze"** = wyciągnięcie z Camoufox **tylko fingerprintu DataDome** (WebGL, Canvas, AudioContext), a resztę przez curl_cffi + lekki silnik JS.

**Randomizacja:** fingerprint musi być **generowany dynamicznie**, ale **spójny z Camoufox** — czyli używać tych samych wartości co Camoufox, ale z losowymi wariacjami.

---

## 2. Architektura

### 2.1 Podział ról

| Komponent | Technologia | Rola |
|---|---|---|
| **Fingerprint DataDome** | Camoufox (C++) | WebGL, Canvas, AudioContext — tylko to, czego nie da się zrobić w Node.js |
| **Token Incognia** | Node.js (WebCrypto) | AES-GCM z HKDF — działa w Node.js |
| **Transport** | curl_cffi (Python) | TLS, HTTP/2 — działa w Pythonie |
| **Orkiestracja** | Python (master) | Łączy Camoufox, Node.js, curl_cffi |

### 2.2 Przepływ danych

```
[Camoufox] → fingerprint DataDome (WebGL, Canvas, AudioContext)
     ↓
[Node.js] → token Incognia (AES-GCM z HKDF)
     ↓
[curl_cffi] → request payment z fingerprintem + tokenem
     ↓
[Serwer Vinted] → 200 OK
```

---

## 3. Język dla "asysty" — rekomendacja

### 3.1 Opcje

| Język | Zalety | Wady | Rekomendacja |
|---|---|---|---|
| **Python** | Naturalny dla curl_cffi, łatwy w integracji | Słaby dla WebGL/Canvas | ✅ **Master** — orkiestracja |
| **Node.js** | Dobry dla WebCrypto | Słaby dla WebGL/Canvas | ✅ **Token** — AES-GCM |
| **C++** | Najlepszy dla WebGL/Canvas | Trudny w integracji | ⚠️ **Tylko dla fingerprintu** — jeśli Camoufox nie wystarcza |

### 3.2 Rekomendacja: Python jako master

**Python** jako język główny (master), wywołujący:
- **Node.js** dla tokena Incognia (WebCrypto)
- **C++** dla fingerprintu DataDome (jeśli Camoufox nie wystarcza)

**Uzasadnienie:**
- Python jest naturalny dla curl_cffi (transport)
- Python łatwo integruje się z Node.js (subprocess) i C++ (ctypes/cffi)
- Python pozwala na prostą orkiestrację

---

## 4. Randomizacja fingerprintu — spójność z Camoufox

### 4.1 Problem

Fingerprint DataDome musi być **randomizowany** (żeby nie był stały), ale **spójny z Camoufox** (żeby DataDome nie wykrył rozjazdu).

### 4.2 Rozwiązanie

**Użycie tych samych wartości co Camoufox, ale z losowymi wariacjami:**

```python
# Przykład: WebGL fingerprint z Camoufox + losowa wariacja
webgl_vendor = camoufox_webgl_vendor  # z Camoufox
webgl_renderer = camoufox_webgl_renderer  # z Camoufox
# Losowa wariacja: zmiana ostatnich cyfr w renderingu
webgl_renderer_randomized = webgl_renderer[:-3] + str(random.randint(100, 999))
```

**Kluczowe:** wariacja musi być **subtelna** — wystarczająca, żeby nie być stałym, ale nie na tyle duża, żeby DataDome wykrył oszustwo.

---

## 5. Implementacja

### 5.1 Pliki

| Plik | Rola |
|---|---|
| `master_orchestrator.py` | Python — orkiestracja Camoufox, Node.js, curl_cffi |
| `fingerprint_harvester.py` | Python — wyciąga fingerprint z Camoufox |
| `generate_incognia_token.js` | Node.js — generuje token Incognia |
| `payment_sender.py` | Python — wysyła payment przez curl_cffi |

### 5.2 Przepływ

1. **Fingerprint harvest** — Camoufox → WebGL, Canvas, AudioContext
2. **Token generation** — Node.js → AES-GCM z HKDF
3. **Payment** — curl_cffi → POST /checkout/payment z fingerprintem + tokenem

---

## 6. Wniosek

**"Zajeb z przeglądarki tylko to co najlepsze"** = Camoufox dla fingerprintu DataDome, Node.js dla tokena Incognia, curl_cffi dla transportu.

**Język dla asysty:** **Python** jako master, z wywołaniami Node.js (WebCrypto) i C++ (WebGL/Canvas, jeśli potrzebne).

**Randomizacja:** fingerprint generowany dynamicznie, ale spójny z Camoufox — używa tych samych wartości, ale z losowymi wariacjami.

---

**Koniec analizy.**
