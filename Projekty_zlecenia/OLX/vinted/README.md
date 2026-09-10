# Vinted Bot — Workspace

> Automatyczny system zakupów na Vinted.pl — pokonać kops.gg przy 50% niższych kosztach.

---

## Quickstart (dla nowych agentów/devów)

1. **Przeczytaj reguły**: [`AGENTS.md`](AGENTS.md) — biblia agentów (zasady, struktura, hierarchy of truth)
2. **Sprawdź stan**: [`vinted/testy_camoufox/docs/SYNTEZA_GŁÓWNA.md`](vinted/testy_camoufox/docs/SYNTEZA_GŁÓWNA.md) — aktualny status projektu
3. **Mapa konflików**: [`vinted/raporty/00_POWTORZENIA_I_SPRZECZNOSCI.md`](vinted/raporty/00_POWTORZENIA_I_SPRZECZNOSCI.md)
4. **Źródło prawdy**: [`vinted/dane/captured_requests.json`](vinted/dane/captured_requests.json)

---

## Struktura projektu

```
vinted-bot/
├── bot/                          # Kod produkcyjny MVP (Python)
│   ├── src/vintedbot/            # 14 modułów (checkout, detection, incognia, ...)
│   └── tests/                    # CLI e2e + unit
│
├── vinted/                       # Badania i dowody
│   ├── dane/                     # captured_requests.json, HAR, JS chunks, APK
│   ├── raporty/                  # Raporty (01-07 kategorie)
│   └── testy_camoufox/           # Front badań: docs/, tools/, testing/
│
├── archive/                      # Archiwum (NIGDY nie usuwane — tylko archive)
│
├── AGENTS.md                     # Reguły agentów
└── README.md                     # Ten plik
```

Pełna mapa: [`MENTAL_MAP_SYSTEM.md`](MENTAL_MAP_SYSTEM.md).

---

## Komponenty

| Komponent | Ścieżka | Opis |
|-----------|---------|------|
| Bot CLI | `bot/src/vintedbot/cli.py` | Punkt wejścia (`python -m vintedbot`) |
| Checkout | `bot/src/vintedbot/checkout.py` | Flow budowania transakcji |
| Detection | `bot/src/vintedbot/detection.py` | Wykrywanie ofert (filtr, kategoryzacja) |
| Incognia | `bot/src/vintedbot/incognia.py` | Generator tokenu JWE |
| Testy | `bot/tests/test_cli_e2e.py` | CLI e2e przez `CliRunner` |
| Walidator dokumentacji | `vinted/testy_camoufox/tools/validate_confidence_tags.py` | Sprawdza oznaczenia [UDOWODNIONE] |

---

## Konwencje

### Commity (Conventional Commits)

```
feat(checkout): add JWE token generator
fix(api): correct DataDome header order
docs(synteza): update CHECKOUT_KONFLIKTY.md
chore(archive): git mv validate_*.py
```

Pełna tabela typów: [AGENTS.md sekcja 8](AGENTS.md#8-nakaz-konwencja-commitów-conventional-commits).

### Oznaczenia pewności (w dokumentacji)

| Tag | Znaczenie |
|-----|----------|
| `[UDOWODNIONE]` | potwierdzone twardymi dowodami (captured_requests.json) |
| `[POTWIERDZONE]` | potwierdzone analizą istniejących danych |
| `[DOMNIEMANE]` | ekspercka ocena / analiza kodu JS |
| `[HIPOTEZA]` | hipoteza bez testów |
| `[NIEPOTWIERDZONE]` | niezweryfikowane, brak dowodów |
| `[NAKAZ]` | nakaz systemowy (proceduralny) |

Walidator: `python vinted/testy_camoufox/tools/validate_confidence_tags.py --ci-only`

---

## Komendy

```bash
# Uruchom bota (po skonfigurowaniu kont)
python -m vintedbot

# Waliduj dokumentację (CI tryb)
python vinted/testy_camoufox/tools/validate_confidence_tags.py --ci-only --json

# Testy bota
cd bot && pytest tests/ -v

# Sprawdź archiwum (co zostało przeniesione)
git log --diff-filter=R --summary | head -20
```

---

## Status projektu (2026-09-01)

| Metryka | Status | Źródło |
|---------|:------:|--------|
| API katalogu (200) | ✅ | `captured_requests.json` |
| Rate-limit ~0.83 req/s | ✅ | `captured_requests.json` |
| DataDome bypass | ✅ ROZWIĄZANY | slider solver + `profil_firefox_135` |
| Checkout flow | ✅ build=200 | 25/25 deterministycznie (2026-09-02) |
| Payment | ❌ 400 err 114 | Brak karty/portfela na koncie testowym |
| Incognia token | ✅ | `bot/src/vintedbot/incognia.py` |
| kops.gg porównanie | ✅ | Detection ~0.4s vs kops 2.3s |

Pełny status: [`SYNTEZA_GŁÓWNA.md`](vinted/testy_camoufox/docs/SYNTEZA_GŁÓWNA.md).

---

## Zasady bezpieczeństwa

**ABSOLUTNY ZAKAZ** commitowania:
- `cookies_*.txt`, `*_session*.json`, `*token*.js`
- `.har` z wrażliwymi danymi
- profile Firefox (`*.sqlite*`, `*.sqlite-wal`)
- `*.env`, klucze API

Sprawdź przed commitem: `git status --ignored | grep -E '(cookies|sqlite|har|datadome)'`

---

## Ostatnia aktualizacja

2026-09-02 · Status: build/pickup=200 (25/25 live), rezerwacja <4s, payment 114 otwarty
