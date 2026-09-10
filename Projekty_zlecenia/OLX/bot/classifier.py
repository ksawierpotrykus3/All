"""Klasyfikator ofert: twarde kategorie + blacklisty tytulowe.

Kategorie zweryfikowane sonda na zywo:
  2298 = iPhone (100%, 65/65), 3102 = MacBook (100%).
  Auta: category.type == "automotive" + sygnatura pelnego auta.
"""

import re

from . import config
from .logger import LOG_APP

# iPhone: tylko akcesoria + cegły bezużyteczne (iCloud/lock).
# Uszkodzenia fizyczne są WYMAGANE przez klienta ("wszystkie stany, uszkodzone"),
# więc ich tu NIE odrzucamy.
BLACKLIST_IPHONE = [
    "etui", "szkło", "szklo", "obudowa", "case", "karta sim", "karta-sim",
    "ładowarka", "ladowarka", "słuchawki", "sluchawki", "uchwyt", "folia",
    "akcesori", "pop socket", "stacjonarn",
    "icloud", "zablokowany", "zablokowana", "lock", "locked", "hasło", "haslo",
]

# iPhone: mapowanie model -> widełki cenowe (min, max) od klienta.
# Kolejność ma znaczenie: bardziej specyficzne wzorce PRZED ogólnymi
# (np. "13 pro max" przed "13 pro" przed "13").
IPHONE_MODELS = [
    (r"\b14\s*pro\s*max\b", 100, 1050),
    (r"\b14\s*pro\b", 100, 1050),
    (r"\b14\s*plus\b", 60, 655),
    (r"\b14\b", 60, 655),
    (r"\b13\s*pro\s*max\b", 100, 800),
    (r"\b13\s*pro\b", 100, 800),
    (r"\b13\s*mini\b", 0, 450),
    (r"\b13\b", 0, 450),
    (r"\b12\s*pro\s*max\b", 0, 400),
    (r"\b12\s*pro\b", 0, 400),
    (r"\b12\s*mini\b", 0, 280),
    (r"\b12\b", 0, 280),
    (r"\b16\s*pro\b", 0, 1400),
    (r"\b16\s*plus\b", 0, 1400),
    (r"\b16\s*e\b", 0, 1400),
    (r"\b16\b", 0, 1400),
    (r"\b17\s*air\b", 200, 2000),
    (r"\b17\s*e\b", 240, 1850),
    (r"\b17\b", 200, 2000),
    (r"\b15\s*pro\s*max\b", 160, 1650),
    (r"\b15\s*pro\b", 160, 1650),
    (r"\b15\s*plus\b", 100, 1000),
    (r"\b15\b", 100, 1000),
]

# MacBook: akcesoria + uszkodzone
BLACKLIST_MACBOOK = [
    "etui", "szkło", "szklo", "obudowa", "case", "ładowarka", "ladowarka",
    "słuchawki", "sluchawki", "uchwyt", "folia", "akcesori",
    "uszkodzony", "uszkodzona", "zbity", "zbita", "pęknięty", "pekniety",
    "zalany", "zalana", "zablokowany", "locked", "dawca", "na części",
    "na czesci", "do naprawy", "icloud", "hasło", "haslo",
]

# Stop-listy do wyciagania marki auta / frazy wyszukiwania z tytulu
STOPWORDS_BRAND = {
    "sprzedam", "sprzedaż", "sprzedaz", "auto", "samochód", "samochod",
    "osobowy", "używane", "uzywane", "używany", "uzywany", "nowy", "nowe",
    "nowa", "poleasingowy", "leasing", "rocznik", "stan", "idealny",
    "bezwypadkowy", "pierwszy", "właściciel", "wlasciciel", "witam",
    "witam,", "na", "posiadam", "okazja", "zadbana",
}


def _price(offer):
    for p in offer.get("params", []) or []:
        if p.get("key") == "price":
            return p.get("value", {}).get("value")
    return None


def parse_price(value):
    """Normalizuj cene do float. Obsluguje '12000', '12 000', '12000.50'."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    s = s.replace("zł", "").replace("zl", "").replace(" ", "").replace("\xa0", "")
    if "," in s and "." in s:
        s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _region(offer):
    return (offer.get("location") or {}).get("region", {}).get("name", "")


def _partner(offer):
    return (offer.get("partner") or {}).get("code")


def _param_keys(offer):
    return {p.get("key") for p in (offer.get("params") or [])}


def is_full_car(offer):
    """Pelne auto osobowe, nie czesc/akcesorium."""
    keys = _param_keys(offer)
    if "parts_category" in keys or "part_number" in keys:
        return False
    markers = {"year", "milage", "petrol", "car_body", "transmission", "vin"}
    return len(keys & markers) >= 3


def pick_brand(title):
    """Wydobadz marke z tytulu auta; pomija stop-slowo."""
    for w in title.split():
        w_clean = re.sub(r"[^\wąćęłńóśźżĄĆĘŁŃÓŚŹŻ0-9-]", "", w.lower())
        if w_clean and w_clean not in STOPWORDS_BRAND:
            return w_clean
    return "bmw"


def search_phrase(title):
    """Precyzyjna fraza do komparatora (pierwsze 4 znaczace slowa)."""
    words = []
    for w in title.split():
        w_clean = re.sub(r"[^\wąćęłńóśźżĄĆĘŁŃÓŚŹŻ0-9-]", "", w.lower())
        if w_clean and w_clean not in STOPWORDS_BRAND:
            words.append(w_clean)
        if len(words) >= 4:
            break
    return " ".join(words) if words else title.strip()


def classify(offer):
    """Zwroc (query, label) jesli oferta pasuje do twardych filtrow, inaczej None."""
    cat_id = (offer.get("category") or {}).get("id")
    title = offer.get("title") or ""
    t = title.lower()

    if cat_id == config.IPHONE_CAT_ID:
        for w in BLACKLIST_IPHONE:
            if w in t:
                LOG_APP.debug(f"odrzucono id={offer.get('id')} powód=blacklist_iphone({w})")
                return None
        p = parse_price(_price(offer))
        if p is None:
            LOG_APP.debug(f"odrzucono id={offer.get('id')} powód=brak_ceny_iphone")
            return None
        for pattern, lo, hi in IPHONE_MODELS:
            if re.search(pattern, t):
                if lo <= p <= hi:
                    return "iphone", "IPHONE"
                LOG_APP.debug(
                    f"odrzucono id={offer.get('id')} powód=cena_iphone("
                    f"{p} poza {lo}-{hi})"
                )
                return None
        LOG_APP.debug(f"odrzucono id={offer.get('id')} powód=model_poza_lista")
        return None

    if cat_id == config.MACBOOK_CAT_ID:
        norm = re.sub(r"\s+", "", t)
        if "macbook" not in t and "mac book" not in t and "macbookpro" not in norm:
            LOG_APP.debug(f"odrzucono id={offer.get('id')} powód=nie_macbook")
            return None
        for w in BLACKLIST_MACBOOK:
            if w in t:
                LOG_APP.debug(f"odrzucono id={offer.get('id')} powód=blacklist_macbook({w})")
                return None
        return "macbook", "MACBOOK"

    if (offer.get("category") or {}).get("type") == "automotive" and is_full_car(offer):
        if _partner(offer) == config.OTOMOTO_PARTNER:
            LOG_APP.debug(f"odrzucono id={offer.get('id')} powód=otomoto_partner")
            return None
        if config.REGION_AUTO not in _region(offer).lower():
            LOG_APP.debug(f"odrzucono id={offer.get('id')} powód=region_auto")
            return None
        p = parse_price(_price(offer))
        if p is None or p > config.MAX_PRICE_AUTO:
            LOG_APP.debug(f"odrzucono id={offer.get('id')} powód=cena_auto({p})")
            return None
        return pick_brand(title), "AUTO"

    return None