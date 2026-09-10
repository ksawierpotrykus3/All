# coding: utf-8
"""
Pomiar tempa kreacji ID na OLX (dowod, czy detektor nadaza).

Metoda:
  1. Pobierz seed max_id z listy.
  2. Przez N sekund skanuj ID w gore (max_id+1, max_id+2, ...),
     licz ile ID zwrocilo 200 (nowe ogloszenia powstale w oknie).
  3. Tempo kreacji = trafienia / sekunda.
  4. Tempo skanowania = przeskanowane / sekunda.

Jesli tempo kreacji > tempo skanowania -> detektor OM I J A nowe oferty.
"""
import sys
import time
from curl_cffi import requests as creq

IMP = "chrome124"
API = "https://www.olx.pl/api/v1/offers/"


def get_json(url, timeout=10):
    try:
        r = creq.get(url, impersonate=IMP, timeout=timeout)
        return r.status_code, (r.json() if r.status_code == 200 else None)
    except Exception as e:  # noqa: BLE001
        return -1, str(e)


def get_max_id():
    code, j = get_json(API + "?offset=0&limit=50")
    if code != 200 or not j:
        return None
    return max(d["id"] for d in j.get("data", []))


def main(duration=60):
    mx = get_max_id()
    if mx is None:
        print("brak seed")
        return
    print(f"seed max_id={mx}")
    print(f"skan przez {duration} s w gore...")

    end = time.time() + duration
    oid = mx + 1
    scanned = 0
    hits = 0
    codes = {}
    t0 = time.time()

    while time.time() < end:
        code, _ = get_json(API + str(oid) + "/")
        scanned += 1
        codes[code] = codes.get(code, 0) + 1
        if code == 200:
            hits += 1
            print(f"  NOWE trafienie id={oid}")
        oid += 1
        time.sleep(0.1)  # ~10 req/s (limit testu)

    dt = time.time() - t0
    print(f"\n=== WYNIK ===")
    print(f"przeskanowano={scanned} w {dt:.1f}s")
    print(f"tempo skanowania={scanned/dt:.2f} ID/s")
    print(f"nowe ogloszenia (200)={hits}")
    print(f"tempo kreacji={hits/dt:.3f} ID/s (w oknie pomiaru)")
    print(f"statusy: {codes}")

    if hits / dt >= scanned / dt:
        print("WNIOSEK: detektor NIE nadaza - tempo kreacji >= tempo skanowania")
    else:
        print(f"WNIOSEK: detektor nadaza, zapas={(scanned/dt) - (hits/dt):.2f} ID/s")


if __name__ == "__main__":
    dur = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    main(dur)