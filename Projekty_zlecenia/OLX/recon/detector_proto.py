# coding: utf-8
"""
Prototyp bota OLX (faza 1) - skanowanie ID w górę + detekcja kategorii.
Wszystko w logach i konsoli. Zero powiadomień.
"""
import json
import time
import datetime
from curl_cffi import requests as creq

IMP = "chrome124"
API = "https://www.olx.pl/api/v1/offers/"

# Kategorie, które nas interesują (category.id w JSON)
KAT = {
    203: "Auta",
    2912: "Telefony",
}

LOG_FILE = r"C:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\recon\detect.log"


def log(msg):
    line = f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def get_offer(oid):
    try:
        r = creq.get(API + str(oid) + "/", impersonate=IMP, timeout=15)
        return r.status_code, (r.json() if r.status_code == 200 else None)
    except Exception as e:
        return -1, str(e)


def get_max_id():
    try:
        r = creq.get(API + "?offset=0&limit=50", impersonate=IMP, timeout=20)
        if r.status_code != 200:
            return None, f"list status={r.status_code}"
        j = r.json()
        data = j.get("data", [])
        ids = [d["id"] for d in data]
        return (max(ids), ids) if ids else (None, data)
    except Exception as e:
        return None, str(e)


def probe_future_ids(base, count=20):
    """Sprawdź, co zwracają ID większe od bazowego."""
    results = {}
    for oid in range(base + 1, base + 1 + count):
        code, _ = get_offer(oid)
        results[oid] = code
    return results


if __name__ == "__main__":
    print("=" * 60)
    print("Prototyp OLX - faza 1 (detekcja ID)")
    print("=" * 60)

    # 1. Test nieistniejącego ID (bardzo duży)
    print("\n[TEST] Nieistniejące ID (duże):")
    code, body = get_offer(9999999999)
    print(f"  kod={code} body={str(body)[:120]}")

    # 2. Pobierz max ID
    print("\n[TEST] Pobieranie max ID z listy...")
    mx, ids = get_max_id()
    print(f"  max_id={mx}")
    if ids:
        print(f"  próbka ID: {ids[:5]}")

    # 3. Sonda przyszłych ID
    if mx:
        print(f"\n[TEST] Sondowanie {mx+1} .. {mx+20}")
        res = probe_future_ids(mx)
        for oid, code in sorted(res.items()):
            print(f"  id={oid} -> {code}")