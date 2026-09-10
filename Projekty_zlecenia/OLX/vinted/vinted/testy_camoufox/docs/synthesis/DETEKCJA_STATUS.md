# SYNTEZA: Status warstwy detekcji Vinted

## 📊 **FAKTY UDOWODNIONE (zgoda wszystkich dokumentów)**

### ✅ Katalog API
- **Endpoint:** `GET /api/v2/catalog/items` → HTTP 200
- **Paginacja:** `per_page` max 96, `total_entries` max 960
- **Rate-limit:** ~0.83 req/s (30 req co 0.15s → 429 po 6. requeście)
- **Filtry działające:** `brand_ids`, `size_ids`, `status_ids`, `search_text`
- **Filtr kategorii:** [UDOWODNIONE] NIE działa w API, tylko przez HTML SSR

### ✅ Szczegóły oferty
- `GET /api/v2/items/{id}` → 404
- `GET /details` → 403 (DataDome)
- `GET /items/{id}` → 200 (HTML z JSON-LD, ~1.95 MB)

### ✅ Wymagania TLS/JA4
- Wymagana emulacja `curl_cffi chrome124`
- Bez tego → natychmiastowy 403 DataDome/Cloudflare

## 🎯 **WNIOSKI OPERACYJNE**

### Co MOŻEMY robić:
1. **Monitorowanie katalogu** - pełna funkcjonalność
2. **Filtrowanie według marki/rozmiaru** [UDOWODNIONE] - działa
3. **Pobieranie szczegółów** - przez HTML scraping
4. **Rate-limiting** - 1 request na 1.2s bezpiecznie

### Czego NIE MOŻEMY (jeszcze) — stan 2026-08-31, AKTUALIZACJA 2026-09-01/02:
1. **Płatności (payment=200)** - nieudowodnione, error 114 (brak karty/portfela na koncie testowym) [POTWIERDZONE]
2. **Automatyczne zakupy (checkout/build=200)** - [MIT] (aktualizacja 2026-09-01: ROZWIĄZANE — slider solver + `profil_firefox_135`, 25/25), zob. CHECKOUT_KONFLIKTY.md
3. **Pominięcie DataDome** - [MIT] (aktualizacja 2026-09-01: ROZWIĄZANE sliderem, nie wymaga stabilnego fingerprintu canvas)

## 📈 **METRYKI WERYFIKOWANE**

| Metryka | Wartość | Źródło |
|---------|---------|---------|
| Rate-limit | 0.83 req/s | `01_sonda_api/` |
| Max items/page | 96 | `01_sonda_api/` |
| ID losowe | Tak (43↑/52↓) | `03_weryfikacja/` |
| TLS requirement | Chrome 124 | `04_niewiadome/` |

## 🚀 **NASTĘPNE KROKI**

1. **Potwierdzić endpointy checkout** - brakujące dowody
2. **Rozwiązać DataDome 403** - fingerprint przeglądarki
3. **Zmierzyć rzeczywisty czas zakupu** - vs marketing kops.gg

---

**Źródła:** `01_sonda_api/`, `03_weryfikacja/`, `04_niewiadome/`, `00_POWTORZENIA_I_SPRZECZNOSCI.md`
**Ostatnia aktualizacja:** 2026-08-31
**Status:** SPÓJNE FAKTY