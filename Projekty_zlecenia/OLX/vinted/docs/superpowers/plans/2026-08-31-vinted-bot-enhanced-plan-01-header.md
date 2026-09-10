# Enhanced Vinted Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement enhanced Vinted Bot with full account isolation, residential proxy support, and checkout breakthrough to satisfy client requirements from rozmowa_smartcare.md

**Architecture:** Enhanced curl_cffi with full browser fingerprint + residential proxy rotation + multiprocess account isolation + YAML config management + benchmark collection system

**Tech Stack:** Python 3.11+, curl_cffi, Click, Pydantic, multiprocessing, YAML, pytest

**Client Requirements:** 
1. Ultra-high speed (faster than kops.gg)
2. No Discord + CLI/web interface
3. Advanced filters (brand, condition, price, keywords, categories, sizes)
4. Multi-account (3-4 accounts simultaneously)
5. Ban protection (residential proxy + fingerprint spoofing)
6. Real speed measurements

**Project Status:**
- ✅ Detection layer works (curl_cffi FF152 fingerprint)
- ✅ Basic filters work (brand, size, status, price, search_text)
- ❌ Checkout blocked by DataDome 403
- ❌ No residential proxy support
- ❌ No full account isolation
- ❌ No real benchmark measurements

**Main Blocker:** DataDome 403 on checkout despite correct tokens (CSRF, anon_id, Incognia JWE)

**Solution Strategy:** Systematic checkout experiments with different fingerprint combinations + enhanced headers

---

## FILE STRUCTURE OVERVIEW

### New Files to Create:
1. `bot/src/vintedbot/fingerprint_enhancer.py` - Enhanced browser fingerprint
2. `bot/src/vintedbot/proxy_manager.py` - Residential proxy rotation
3. `bot/src/vintedbot/account_worker.py` - Isolated account processes
4. `bot/src/vintedbot/cli_extended.py` - Extended CLI with YAML configs
5. `bot/src/vintedbot/benchmark_collector.py` - Real benchmark measurements
6. `bot/src/vintedbot/checkout_experiment.py` - DataDome bypass experiments
7. `bot/config/accounts/*.yaml` - Account configuration files
8. `bot/tests/test_fingerprint_enhancer.py` - Tests for fingerprint
9. `bot/tests/test_proxy_manager.py` - Tests for proxy manager

### Files to Modify:
1. `bot/src/vintedbot/config.py` - Add proxy/fingerprint config constants
2. `bot/src/vintedbot/detection.py` - Integrate enhanced fingerprint
3. `bot/src/vintedbot/checkout.py` - Use enhanced sessions
4. `bot/pyproject.toml` - Add new dependencies
5. `bot/tests/conftest.py` - Add test fixtures for new modules

### Roadmap (7 weeks total):
- **Phase 1 (2 weeks):** Enhanced fingerprint + checkout experiments + benchmarks
- **Phase 2 (3 weeks):** Residential proxy + account isolation + extended CLI
- **Phase 3 (2 weeks):** Evidence system + alerts + deployment

---

**Next:** Detailed task breakdown in separate files