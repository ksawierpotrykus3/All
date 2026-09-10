# coding: utf-8
"""Benchmark DETEKCJI (S1 warm/cold + S2 wplyw per_page) przez curl_cffi.

Wylacznie GET /api/v2/catalog/items - warstwa detekcyjna, ZERO transakcji
(brak conversations/build/payment), wiec nie ryzykuje soft-banu DataDome.

Mierzy:
  S1 - warm (jedna Session) vs cold (nowa Session per request): p50/p95/avg
  S2 - per_page=2 vs 10 vs 24: czas + rozmiar odpowiedzi
"""
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from curl_cffi import requests as cr

BASE_DIR = Path(__file__).resolve().parent
COOKIES_PATH = BASE_DIR / "cookies_profil.json"
IMPERSONATE = "chrome136"  # potwierdzony 200 w pomiar_czasu_curl_out.json

CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"
H = {"x-csrf-token": CSRF, "x-anon-id": ANON}

URL_BASE = ("https://www.vinted.pl/api/v2/catalog/items"
            "?catalog_ids%5B%5D=44&price_to=50&order=newest_first&page=1&currency=PLN")


def _headers():
    return {
        "accept": "application/json,text/plain,*/*,image/webp",
        "accept-language": "pl,en-US;q=0.9,en;q=0.8,ru;q=0.7",
        "content-type": "application/json",
        "locale": "pl-PL",
        "origin": "https://www.vinted.pl",
        "referer": "https://www.vinted.pl/",
        "priority": "u=3",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
    }


def _session():
    s = cr.Session()
    if COOKIES_PATH.exists():
        for c in json.loads(COOKIES_PATH.read_text(encoding="utf-8")):
            try:
                s.cookies.set(c["name"], c["value"],
                              domain=c.get("domain", ""), path=c.get("path", "/"))
            except Exception:
                pass
    s.headers.update(_headers())
    return s


def _get_ms(s, per_page):
    url = URL_BASE + f"&per_page={per_page}"
    t0 = time.monotonic()
    r = s.get(url, headers=H, impersonate=IMPERSONATE, timeout=30)
    dt = (time.monotonic() - t0) * 1000
    return dt, r.status_code, len(r.content)


def _stats(times):
    return {
        "n": len(times),
        "avg_ms": round(statistics.mean(times), 1),
        "p50_ms": round(statistics.median(times), 1),
        "p95_ms": round(sorted(times)[int(len(times) * 0.95) - 1], 1) if len(times) >= 20
        else round(max(times), 1),
        "min_ms": round(min(times), 1),
        "max_ms": round(max(times), 1),
    }


def s1_warm_vs_cold(n=5):
    """Warm: jedna sesja. Cold: nowa sesja per request."""
    warm_times, cold_times = [], []
    warm_s = _session()
    for _ in range(n):
        dt, _, _ = _get_ms(warm_s, 2)
        warm_times.append(dt)
    for _ in range(n):
        dt, _, _ = _get_ms(_session(), 2)
        cold_times.append(dt)
    return {"warm": _stats(warm_times), "cold": _stats(cold_times)}


def s2_per_page(sizes=(2, 10, 24)):
    s = _session()
    out = []
    for pp in sizes:
        dt, status, nbytes = _get_ms(s, pp)
        out.append({
            "per_page": pp,
            "ms": round(dt, 1),
            "http": status,
            "bytes": nbytes,
            "kb": round(nbytes / 1024, 1),
        })
    return out


def _health_check():
    """GET /users/current — jezeli !=200, sesja/token niewazny, abort."""
    s = _session()
    r = s.get("https://www.vinted.pl/api/v2/users/current",
              headers=H, impersonate=IMPERSONATE, timeout=30)
    return r.status_code, r.text[:120]


def main():
    hc_status, hc_body = _health_check()
    if hc_status != 200:
        print(f"[ABORT] /users/current -> HTTP {hc_status}: {hc_body}", flush=True)
        return
    print(f"[OK] sesja zalogowana (/users/current -> 200)", flush=True)

    results = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "impersonate": IMPERSONATE,
        "s1_warm_vs_cold": None,
        "s2_per_page": None,
    }
    print("== S1: warm vs cold (GET /catalog/items, per_page=2) ==", flush=True)
    results["s1_warm_vs_cold"] = s1_warm_vs_cold()
    print(json.dumps(results["s1_warm_vs_cold"], indent=2), flush=True)

    print("== S2: wplyw per_page ==", flush=True)
    results["s2_per_page"] = s2_per_page()
    print(json.dumps(results["s2_per_page"], indent=2), flush=True)

    out = BASE_DIR / "wynik_bench_detection.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nZapisano: {out}", flush=True)


if __name__ == "__main__":
    main()