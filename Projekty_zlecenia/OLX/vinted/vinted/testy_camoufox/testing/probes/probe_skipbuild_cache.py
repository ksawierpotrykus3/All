# coding: utf-8
"""Bezpieczne pomiary (GET, bez nowej transakcji).

1. V3 skip-build: czy stara transakcja (po buildzie) ma purchase_id nie-null?
2. Spójność point_code/rate_uuid między runami (cache'owalność punktu odbioru).
"""
import json
import time
from pathlib import Path

from curl_cffi import requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"
IMP = "chrome136"
H = {"x-csrf-token": CSRF, "x-anon-id": ANON}

# stare transakcje z poprzednich flow (zapewnione: transakcja istnieje po buildzie)
OLD_TXNS = [21919244429, 21918958364, 21916604367]


def _session():
    s = cr.Session()
    for c in json.loads((BASE_DIR / "cookies_profil.json").read_text(encoding="utf-8")):
        try:
            s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
        except Exception:
            pass
    s.headers.update({"accept": "application/json", "locale": "pl-PL"})
    return s


def main():
    s = _session()
    r = s.get("https://www.vinted.pl/api/v2/users/current", headers=H, impersonate=IMP, timeout=30)
    print("health:", r.status_code)
    if r.status_code != 200:
        print("ABORT", r.text[:120])
        return

    for txn in OLD_TXNS:
        t = time.monotonic()
        r = s.get(f"https://www.vinted.pl/api/v2/transactions/{txn}",
                  headers=H, impersonate=IMP, timeout=30)
        dt = (time.monotonic() - t) * 1000
        try:
            tr = r.json().get("transaction", {})
            print(f"txn {txn}: http={r.status_code} | {dt:.0f} ms | "
                  f"purchase_id={tr.get('purchase_id')!r} | status={tr.get('status')} | "
                  f"status_title={tr.get('status_title')}")
        except Exception:
            print(f"txn {txn}: http={r.status_code} | {dt:.0f} ms | raw={r.text[:150]}")


if __name__ == "__main__":
    main()