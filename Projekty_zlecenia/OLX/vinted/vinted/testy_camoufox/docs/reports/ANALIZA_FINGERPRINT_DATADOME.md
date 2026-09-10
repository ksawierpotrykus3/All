# Analiza: Pełny fingerprint DataDome dla curl i lekkiego silnika JS

**Data:** 2026-08-30
**Status:** Analiza techniczna — czy stack C++/Rust/Julia może zastąpić przeglądarkę dla DataDome

---

## 1. Problem

Payment wymaga pełnego fingerprintu DataDome, który obejmuje:
- **WebGL** (unmasked vendor/renderer, extensions)
- **Canvas** (2D context, toDataURL)
- **AudioContext** (OfflineAudioContext, fingerprint)
- **OffscreenCanvas** (WebGL w workerze)
- **trustToken** (Chrome-only, nie Firefox)

Cookie jar z Camoufox **wystarcza dla build**, ale **nie dla payment** (403 DataDome).

---

## 2. Analiza stacków alternatywnych

### 2.1 C++ (biblioteki WebGL/Canvas)

| Biblioteka | Co daje | Ograniczenie |
|---|---|---|
| **headless-gl** (Node) | WebGL 1.0 w Node | **SwiftShader** (software rendering) — łatwo wykrywalny przez DataDome |
| **skia** (C++) | Canvas 2D | **Nie to samo co przeglądarka** — inny fingerprint (brak GPU, inne czcionki) |
| **node-canvas** | Canvas 2D (Cairo) | **Inny fingerprint** niż przeglądarka (Cairo ≠ Skia) |

**Wniosek:** C++ daje WebGL/Canvas, ale **fingerprint jest inny** niż przeglądarka — DataDome to wykrywa.

### 2.2 Rust

| Biblioteka | Co daje | Ograniczenie |
|---|---|---|
| **wgpu** | WebGPU (nie WebGL) | **Nie WebGL** — inny standard, niekompatybilny z DataDome |
| **raqote** | Canvas 2D | **Inny fingerprint** niż przeglądarka |
| **rust-headless-chrome** | Sterowanie Chrome | **To nie jest lekki silnik** — to pełna przeglądarka |

**Wniosek:** Rust nie daje pełnego fingerprintu przeglądarki — brak WebGL zgodnego z DataDome.

### 2.3 Julia

| Biblioteka | Co daje | Ograniczenie |
|---|---|---|
| **Luxor.jl** | Grafika 2D | **Nie WebGL/Canvas** — nie nadaje się do fingerprintu |
| **Makie.jl** | Wizualizacja | **Nie WebGL** — inny standard |

**Wniosek:** Julia nie jest przeznaczona do fingerprintu przeglądarki — brak bibliotek WebGL/Canvas.

---

## 3. Wniosek: Żaden stack C++/Rust/Julia nie zastąpi przeglądarki

**Fundamentalny problem:** DataDome wykrywa **software rendering** (SwiftShader, Cairo) i **różnice w fingerprintcie** (czcionki, GPU, timing). Żadna biblioteka C++/Rust/Julia nie da **identycznego fingerprintu** jak przeglądarka.

**Jedyna realna opcja:** przeglądarka (Camoufox) z **CDP (Chrome DevTools Protocol)** lub **rozszerzeniem Firefox** dla payment.

---

## 4. Rekomendacja

| Warstwa | Technologia | Uzasadnienie |
|---|---|---|
| **Token Incognia** | Node.js (AES-GCM) | ✅ Działa (sekcja 22) |
| **Detekcja** | curl_cffi | ✅ Działa (247 ms/req) |
| **Build** | curl_cffi + cookie jar | ✅ Działa (Faza J) |
| **Payment** | **Camoufox (CDP/rozszerzenie)** | ❌ Wymaga pełnego fingerprintu DataDome |

**Payment wymaga przeglądarki** — nie da się tego obejść przez C++/Rust/Julia. Lekki silnik JS pozostaje dla tokena Incognia, nie dla DataDome.

---

## 5. Alternatywa: Camoufox z CDP

Jeśli chcesz uniknąć pełnej przeglądarki dla payment, jedyna opcja to **Camoufox z CDP**:

1. **Camoufox** uruchomiony z `--remote-debugging-port=9222`
2. **CDP** do sterowania (np. `chrome-remote-interface` w Node.js)
3. **Payment przez CDP** — kliknięcie "Zapłać" z `isTrusted=true`

To jest **lżejsze** niż pełna przeglądarka, ale **cięższe** niż curl_cffi — wymaga uruchomionej przeglądarki w tle.

---

**Koniec analizy.**
