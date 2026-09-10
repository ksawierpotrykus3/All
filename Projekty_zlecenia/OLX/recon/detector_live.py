# coding: utf-8
"""
Detektor OLX - faza 2 (live): skanowanie ID w górę + filtrowanie kategorii.
Wykrywa nowe ogłoszenia (auta, telefony) zanim trafią do wyszukiwarki.
Wszystko w logach + konsola. Zero powiadomień.
"""
import json
import time
import datetime
from curl_cffi import requests as creq

IMP = "chrome124"
API = "https://www.olx.pl/api/v1/offers/"

# Kategorie, które nas interesują (category.id w JSON)
KAT = {
    203: "AUTA",
    2912: "TELEFONY",
    # laptopów (MacBook) jeszcze nie znamy - do ustalenia
}

# Słowa-klucze do czarnej listy (śmieci w kategorii telefony)
BLACKLIST_TEL = ["etui", "szkło", "szklo", "obudowa", "case", "karta sim", "karta-sim",
                 "ładowarka", "ladowarka", "stacjonarn", "sluchawki", "słuchawki",
                 "akcesori", "pop socket", "uchwyt"]

LOG_FILE = r"C:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\recon\detect.log"


def log(msg):
    line = f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def get_json(url):
    try:
        r = creq.get(url, impersonate=IMP, timeout=15)
        if r.status_code == 200:
            return r.json()
        return None
    except Exception:
        return None


def get_offer(oid):
    j = get_json(API + str(oid) + "/")
    return j


def get_max_id():
    j = get_json(API + "?offset=0&limit=50")
    if not j:
        return None
    data = j.get("data", [])
    if not data:
        return None
    return max(d["id"] for d in data)


def extract(offer):
    """Wyciągnij istotne pola z oferty."""
    cat_id = offer.get("category", {}).get("id")
    if cat_id not in KAT:
        return None

    title = offer.get("title", "")
    t = title.lower()

    # Filtruj śmieci w telefonach
    if cat_id == 2912:
        for w in BLACKLIST_TEL:
            if w in t:
                return None

    price = None
    for p in offer.get("params", []):
        if p.get("key") == "price":
            price = p.get("value", {}).get("value")
            break

    return {
        "id": offer.get("id"),
        "kat": KAT[cat_id],
        "cat_id": cat_id,
        "title": title,
        "price": price,
        "region": offer.get("location", {}).get("region", {}).get("name"),
        "city": offer.get("location", {}).get("city", {}).get("name"),
        "created": offer.get("created_time"),
        "partner": (offer.get("partner") or {}).get("code"),
    }


def scan(start_id, duration_sec=45, step=1):
    """Skanuj ID od start_id w górę przez duration_sec sekund."""
    end_time = time.time() + duration_sec
    oid = start_id
    hits = []
    scanned = 0
    gaps = 0
    while time.time() < end_time:
        offer = get_offer(oid)
        scanned += 1
        if offer:
            info = extract(offer)
            if info and info["partner"] != "otomoto_pl_form":
                hits.append(info)
                log(f"DETEKCJA: id={info['id']} [{info['kat']}] {info['title'][:60]} "
                    f"| cena={info['price']} | {info['region']}/{info['city']} | {info['created']}")
        else:
            gaps += 1
        oid += step
        time.sleep(0.15)  # lekki odstęp
    return scanned, gaps, hits


if __name__ == "__main__":
    print("=" * 70)
    print("Detektor OLX - faza 2 (live skan ID)")
    print("=" * 70)

    mx = get_max_id()
    log(f"START: max_id z listy = {mx}")

    if mx:
        log(f"Rozpoczynam skanowanie od id={mx+1} (45 sekund)...")
        scanned, gaps, hits = scan(mx + 1, duration_sec=45)

        log(f"KONIEC: przeskanowano={scanned}, luki(404)={gaps}, trafienia={len(hits)}")
        print("\n--- PODSUMOWANIE TRAFIEŃ ---")
        for h in hits:
            print(f"  {h['id']} [{h['kat']}] {h['title'][:60]} | {h['price']} zł | {h['region']}")
        if not hits:
            print("  (brak trafień w tym oknie)")