# coding: utf-8
"""Benchmark A/B z naprzemienna kolejnascia: /messaging/main/inquiries vs /conversations.

Tworzy transakcje (bez checkout/build/payment). Uwaga: limit ~2 nowe transakcje/dzien
(sekcja 32.6), wiec ograniczamy liczbe par. Naprzemienna kolejnosc eliminuje efekt
warm-up pojedynczego backendu.
"""
import json
import time
import sys
from pathlib import Path

from curl_cffi import requests as cr

BASE_DIR = Path(__file__).resolve().parent
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"
IMP = "chrome136"
H = {"x-csrf-token": CSRF, "x-anon-id": ANON}


def _session():
    s = cr.Session(impersonate=IMP)
    for c in json.loads((BASE_DIR / "cookies_profil.json").read_text(encoding="utf-8")):
        try:
            s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
        except Exception:
            pass
    s.headers.update({
        "accept": "application/json,text/plain,*/*,image/webp",
        "accept-language": "pl,en-US;q=0.9,en;q=0.8",
        "content-type": "application/json",
        "locale": "pl-PL",
        "origin": "https://www.vinted.pl",
        "referer": "https://www.vinted.pl/",
    })
    return s


def find_item(s, seen):
    url = ("https://www.vinted.pl/api/v2/catalog/items"
           "?catalog_ids%5B%5D=44&price_to=50&order=newest_first&page=1&per_page=60&currency=PLN")
    r = s.get(url, headers=H, impersonate=IMP, timeout=30)
    for it in r.json().get("items", []):
        u = it.get("user", {})
        if not u or it.get("status") == "sold" or it.get("is_visible") is False:
            continue
        if it["id"] in seen:
            continue
        return it["id"], it["user"]["id"]
    return None, None


def main():
    n_pairs = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    s = _session()
    r = s.get("https://www.vinted.pl/api/v2/users/current", headers=H, impersonate=IMP, timeout=30)
    if r.status_code != 200:
        print("ABORT health", r.status_code, r.text[:120], flush=True)
        return

    seen = set()
    results = []
    for i in range(n_pairs):
        for backend in ("nowy", "stary"):  # naprzemiennie, ta sama kolejność co pętla zewn.
            item_id, seller_id = find_item(s, seen)
            if not item_id:
                print("BRAK itemu, koniec", flush=True)
                break
            seen.add(item_id)
            t0 = time.monotonic()
            if backend == "nowy":
                r = s.post("https://api.vinted.pl/messaging/main/inquiries",
                           json={"item_ids": [str(item_id)], "receiver_id": str(seller_id)},
                           headers=H, impersonate=IMP, timeout=30, allow_redirects=False)
            else:
                r = s.post("https://www.vinted.pl/api/v2/conversations",
                           json={"initiator": "buy", "item_id": str(item_id),
                                 "opposite_user_id": seller_id},
                           headers=H, impersonate=IMP, timeout=30, allow_redirects=False)
            dt = (time.monotonic() - t0) * 1000
            results.append({"pair": i, "backend": backend, "http": r.status_code, "ms": round(dt, 1)})
            print(f"pair={i} {backend:5s} http={r.status_code} {dt:7.1f} ms", flush=True)

    out = BASE_DIR / "wynik_ab_backend.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    # agregacja
    for backend in ("nowy", "stary"):
        vals = [x["ms"] for x in results if x["backend"] == backend and x["http"] == 200]
        if vals:
            avg = sum(vals) / len(vals)
            print(f"{backend:5s} n={len(vals)} avg={avg:.1f} ms", flush=True)


if __name__ == "__main__":
    main()