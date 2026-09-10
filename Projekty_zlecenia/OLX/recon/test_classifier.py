# coding: utf-8
"""
Testy jednostkowe klasyfikatora - zero zaufania, twarde asercje.

Uruchamienie: python test_classifier.py
Wyjscie: PASS/FAIL per przypadek, podsumowanie.

Pokrywa:
  - false positives (smieci, ktore NIE maja byc lapane)
  - false negatives (ciekawe oferty, ktore MAJA byc lapane)
  - parsowanie cen
  - wyciaganie marki
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import monitor_20min as m


def mk(cat_id, title, price=1000, region="Mazowieckie", partner=None, params=None, cat_type="x"):
    if params is None:
        params = [{"key": "price", "value": {"value": price}}]
    return {
        "title": title,
        "category": {"id": cat_id, "type": cat_type},
        "params": params,
        "location": {"region": {"name": region}},
        "partner": {"code": partner} if partner else None,
    }


# pełne auto: params z year/milage/petrol/car_body/transmission
CAR_PARAMS = [
    {"key": "price", "value": {"value": 7900}},
    {"key": "year", "value": {"label": "2008"}},
    {"key": "milage", "value": {"label": "200000 km"}},
    {"key": "petrol", "value": {"label": "Benzyna"}},
    {"key": "car_body", "value": {"label": "Sedan"}},
    {"key": "transmission", "value": {"label": "Manualna"}},
]

# część moto: params z parts_category
PART_PARAMS = [
    {"key": "price", "value": {"value": 200}},
    {"key": "parts_category", "value": {"label": "..."}},
]


def label(offer):
    """Zwraca label z classify (drugi element) lub None."""
    res = m.classify(offer)
    return res[1] if res else None


# (nazwa, oferta, oczekiwany label)  label None = ma byc odrzucone
CASES = [
    # ---- IPHONE: MAJA byc IPHONE
    ("iPhone 14 pro max 128gb", mk(2298, "iPhone 14 pro max 128gb"), "IPHONE"),
    ("Iphone 15 128GB sky blue", mk(2298, "Iphone 15 128GB kolor sky blue"), "IPHONE"),
    ("iPhone SE 2nd gen", mk(2298, "iPhone SE (2nd gen) 64GB"), "IPHONE"),
    ("Telefon iPhone 13", mk(2298, "Telefon iPhone 13 Pro Graphite 128 GB"), "IPHONE"),
    ("Apple 14 Pro bez slowa iphone", mk(2298, "Apple 14 Pro 128GB"), "IPHONE"),
    # ---- IPHONE: smieci, MAJA byc None
    ("iPhone icloud na czesci", mk(2298, "Iphone xs icloud na części w dobrym stanie"), None),
    ("etui iPhone", mk(2298, "Etui iPhone 14 Pro skórzane"), None),
    ("iPhone uszkodzony", mk(2298, "iPhone 12 uszkodzony do naprawy"), None),
    ("iPhone zbity", mk(2298, "iPhone 13 zbity ekran"), None),
    # ---- MACBOOK: MAJA byc MACBOOK
    ("MacBook Pro 15 2017", mk(3102, "MacBook Pro 15\" 2017 | i7 2.9GHz"), "MACBOOK"),
    ("macbook air m2", mk(3102, "MacBook Air M2 8GB"), "MACBOOK"),
    ("MacBookPro bez spacji", mk(3102, "MacBookPro 15 2017 i7"), "MACBOOK"),
    # ---- MACBOOK: smieci, MAJA byc None
    ("etui MacBook", mk(3102, "Etui MacBook Pro 15 2017"), None),
    ("MacBook uszkodzony", mk(3102, "MacBook Air M1 uszkodzony"), None),
    ("Mac Pro (nie MacBook)", mk(3102, "Mac Pro 2013 Xeon"), None),
    ("Mac Mini (nie MacBook)", mk(3102, "Mac Mini M2 16GB"), None),
    # ---- AUTO: cale auta (sygnatura params), MAJA byc AUTO
    ("BMW z Mazowsza (183)", mk(183, "Bmw E60 2.2 170km +lpg", params=CAR_PARAMS, region="Mazowieckie", cat_type="automotive"), "AUTO"),
    ("Opel z Mazowsza (198)", mk(198, "Opel Astra 1.6 benzyna", params=CAR_PARAMS, region="Mazowieckie", cat_type="automotive"), "AUTO"),
    ("VW z Mazowsza (207)", mk(207, "Volkswagen Golf 1.9 TDI", params=CAR_PARAMS, region="Mazowieckie", cat_type="automotive"), "AUTO"),
    ("auto z cena 12000", mk(183, "BMW Seria 3 320d", params=CAR_PARAMS, region="Mazowieckie", cat_type="automotive"), "AUTO"),
    # ---- AUTO: czesci / smieci, MAJA byc None
    ("czesc moto (parts_category)", mk(1465, "Turbina VW", params=PART_PARAMS, region="Mazowieckie", cat_type="automotive"), None),
    ("czesc moto bez sygnatury auta", mk(1399, "Felgi BMW 17", params=[{"key":"price","value":{"value":800}}], region="Mazowieckie", cat_type="automotive"), None),
    ("auto z zlego regionu", mk(183, "BMW E60", params=CAR_PARAMS, region="Małopolskie", cat_type="automotive"), None),
    ("automoto otomoto", mk(183, "BMW E60", params=CAR_PARAMS, region="Mazowieckie", partner="otomoto_pl_form", cat_type="automotive"), None),
]

# Osobne testy funkcji pomocniczych (got = wartosc, expected = wartosc)
FUNC_CASES = [
    ("cena '12 000'", m._parse_price("12 000"), 12000.0),
    ("cena '12000,50'", m._parse_price("12000,50"), 12000.5),
    ("cena '12000'", m._parse_price("12000"), 12000.0),
    ("cena None", m._parse_price(None), None),
    ("marka Opel", m._pick_brand("Opel Astra 1.6 benzyna"), "opel"),
    ("marka BMW", m._pick_brand("Bmw E60 2.2 170km"), "bmw"),
    ("marka Sprzedam Opel", m._pick_brand("Sprzedam Opel Astra"), "opel"),
]


def main():
    passed = 0
    failed = 0

    for name, offer, expected in CASES:
        got = label(offer)
        if got == expected:
            passed += 1
            print(f"  PASS  {name}")
        else:
            failed += 1
            print(f"  FAIL  {name}: got={got!r}, expected={expected!r}")

    for name, got, expected in FUNC_CASES:
        if got == expected:
            passed += 1
            print(f"  PASS  {name}")
        else:
            failed += 1
            print(f"  FAIL  {name}: got={got!r}, expected={expected!r}")

    print(f"\nWynik: {passed} PASS, {failed} FAIL")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()