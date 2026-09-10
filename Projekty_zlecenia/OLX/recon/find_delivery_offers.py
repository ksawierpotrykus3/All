"""Znajdź świeże oferty z dostawą (delivery) do testu checkoutu."""
import json
from pathlib import Path

from curl_cffi import requests as creq

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "dane" / "oferty_z_dostawa.json"

IMP = "chrome124"
CATS = [2298]  # iPhone


def main():
    found = []
    for cat in CATS:
        url = f"https://www.olx.pl/api/v1/offers/?offset=0&limit=50&category_id={cat}"
        r = creq.get(url, impersonate=IMP, timeout=15)
        print(f"cat {cat} -> {r.status_code}")
        if r.status_code != 200:
            continue
        data = r.json()
        for item in data.get("data", []):
            oid = item.get("id")
            delivery = item.get("delivery") or {}
            # szukaj sygnałów dostawy
            signals = {
                k: v for k, v in item.items()
                if any(s in k.lower() for s in ("delivery", "shipping", "courier", "rock"))
            }
            if signals or delivery:
                found.append({"id": oid, "title": item.get("title"), "delivery": delivery, "signals": signals})
                print(f"  offer {oid}: {item.get('title')} delivery={delivery} signals={list(signals)}")

    # tez sprawdz surowa strukture jednej oferty
    if found:
        oid = found[0]["id"]
        r2 = creq.get(f"https://www.olx.pl/api/v1/offers/{oid}/", impersonate=IMP, timeout=15)
        raw = r2.json()
        OUT.write_text(json.dumps({"found": found, "raw_offer": raw}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nSurowa struktura oferty {oid} zapisana do {OUT}")
        # wypisz klucze top-level
        print("Klucze oferty:", list(raw.get("data", {}).keys()))


if __name__ == "__main__":
    main()