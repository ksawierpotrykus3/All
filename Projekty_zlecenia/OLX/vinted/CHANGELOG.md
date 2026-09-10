# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Źródło prawdy:** pełna lista commitów dostępna przez `git log --oneline`.
> Ten plik zawiera tylko **wysokopoziomowe kamienie milowe**.

---

## [Unreleased]

### Added
- Równoległy payment (`O-B`): `POST /checkout/payment` startuje współbieżnie z `PUT pickup_details`/`payment_method` w osobnej sesji curl_cffi (wariant `"payment"`), używając `checksum_build`; przy stale checksum (409) lub wyjątku wykonuje fallback z ostatecznym checksum z odpowiedzi PUT. Zysk ~320 ms na pełny checkout z płatnością.
  - Sesja `"payment"` dodana do `prewarm_sesje` i `upkeep_sesji` w `bot/src/vintedbot/checkout.py`.
  - Priorytet checksum: `pickup_details` > `payment_method` (`if/elif`), zgodnie z intencją dokumentacji.
  - Testy: `test_OB_payment_rownolegle_z_put_pickup_details`, `test_OB_payment_fallback_gdy_checksum_build_stale` (`bot/tests/test_checkout.py`).

### Changed
- W trakcie: standaryzacja workspace'u (archiwizacja, `__init__.py`, `pyproject.toml`).
- `POLL_LIMIT` detekcji 10 → 5 w `bot/src/vintedbot/daemon.py` (P1). [UDOWODNIONE rtt_per_page.json] skraca pętlę pollingu ~30% (−155 ms/poll) bez naruszania rate-limitu.

### Reverted
- Równoległy prewarm sesji (P2) w `bot/src/vintedbot/checkout.py`. [REGRESJA] Burst 4× GET `/users/current` w ~0 ms łamał rate-limit Vinted (~1 req/s) i triggerował DataDome (403) — determinizm checkoutu spadł z 5/5 do 1/5 build=200. Przywrócono prewarm sekwencyjny.

---

## [0.3.0] — 2026-08-31 — Workspace reorganization

### Security
- **[KRYTYCZNE]** Archiwizacja `rozmowa_smartcare.md` (dane wrażliwe/PII) do `archive/2026-08-31_smartcare/`.
- Dodano pre-commit hook blokujący commit `cookies_*.txt`, `*_session*.json`, `*.sqlite*`, `*.har`, `*.env`.

### Added
- Walidator oznaczeń: [`vinted/testy_camoufox/tools/validate_confidence_tags.py`](vinted/testy_camoufox/tools/validate_confidence_tags.py)
  - Skanuje `.md` pod kątem twierdzeń bez `[UDOWODNIONE]/[HIPOTEZA]`.
  - Tryb CI (`--ci-only --json`) do pipeline'ów.
- `pyproject.toml` dla `testy_camoufox/` z wykrytymi zależnościami (curl_cffi, camoufox, cryptography, playwright).
- `__init__.py` w `vinted/narzedzia/`, `vinted/testy_camoufox/tools/`, `vinted/testy_camoufox/testing/`.
- `README.md` z quickstart, konwencjami, statusem projektu.
- `.pre-commit-config.yaml` (62 linie) — hygiene + tag validator + secrets block.
- Sekcja **"Konwencja commitów (Conventional Commits)"** w `AGENTS.md` (nakaz #8).

### Changed
- **Archiwizacja** (NIGDY nie usuwanie): `fix_captured_requests.py`, `validate_agent_rules.py`, `validate_new_mandates.py`, `rozmowa_smartcare.md` → `archive/2026-08-31_*/`.
- `AGENTS.md`: dodano sekcję Conventional Commits z tabelą typów i scope'ów projektu.

### Documentation
- `RAPORT_STATUS_2026-08-29.md`, `DZIENNIK_DZIALAN.md` — bieżące dzienniki postępu.

---

## [0.2.0] — 2026-08-31 — Bot MVP + APK research

### Added
- **Bot MVP** (`bot/src/vintedbot/`):
  - `cli.py` — punkt wejścia CLI.
  - `checkout.py`, `detection.py`, `incognia.py` (generator tokenu JWE).
  - `daemon.py`, `session_state.py`, `refresh_loop.py` — pętla odświeżania + auto-zakup.
  - `autocop.py` — autokup z curl_cffi + flaga `--payment`.
- **APK research data** (`vinted/dane/apk/`):
  - Pełna dekompilacja Vinted 26.33.1 (jadx_out, ~67k plików Java).
  - Extracted resources (`resources.arsc`, manifest, cert SHA256).
- **AGENTS.md mandates** — checkout, evidence tracking, conflict docs.
- Testy CLI: `bot/tests/test_cli_e2e.py` z `CliRunner`.
- Syntezy: `SYNTEZA_CAMOUFOX_FIREFOX.md`, `SYNTEZA_GŁÓWNA.md`, `MCP_RESEARCH_REPORT.md`.
- Raporty inżynierskie: `ANALIZA_INCOGNIA_PLAINTEXT_POZYSKANY.md`, `ENDPOINTY_TRANSAKCYJNE_I_BUILD_BEZ_STRONY.md`, `ANALIZA_PRZYSPIESZENIA_CURL_CFFI_2_3S.md`.

### Changed
- Reorganizacja z `camoufox` na ścieżkę zakupową `curl_cffi` (szybsze, lepszy TLS/JA4 fingerprint).

---

## [0.1.0] — 2026-08-28 — Initial research

### Added
- Pierwsze udokumentowane reverse engineering Vinted API (`vinted/dane/captured_requests.json`).
- Sondy API (`vinted/testy/probe_*.py`) — paginacja, rate-limit, luka w numeracji ofert.
- `AGENTS.md` (pierwsza wersja, ~550 linii).

---

## Legenda oznaczeń pewności

| Tag | Znaczenie |
|-----|----------|
| `[UDOWODNIONE]` | potwierdzone twardymi dowodami (captured_requests.json) |
| `[POTWIERDZONE]` | potwierdzone analizą istniejących danych |
| `[DOMNIEMANE]` | ekspercka ocena / analiza kodu JS |
| `[HIPOTEZA]` | hipoteza bez testów |
| `[NIEPOTWIERDZONE]` | niezweryfikowane |

Pełna dokumentacja: [`AGENTS.md`](AGENTS.md).

[Unreleased]: https://example.com/vinted-bot/compare/v0.3.0...HEAD
[0.3.0]: https://example.com/vinted-bot/compare/v0.2.0...v0.3.0
[0.2.0]: https://example.com/vinted-bot/compare/v0.1.0...v0.2.0
[0.1.0]: https://example.com/vinted-bot/releases/tag/v0.1.0
