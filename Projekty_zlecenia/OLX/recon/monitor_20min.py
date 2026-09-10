# coding: utf-8
"""
Monitor OLX 20 min - faza 3 (live monitoring z dowodami).

Dwa rownolegle watki:
  T1  Detektor ID  - skanuje rosnace numeryczne ID (max_id+1 ... +K) i lapie
                     oferty zanim trafia do publicznej wyszukiwarki.
  T2  Live site    - cyklicznie odpytuje publiczna wyszukiwarke i loguje liczbe
                     zwroconych ofert (dowod, ze strona zyje).

Komparator:
  Dla kazdej oferty zlapanej przez detektor sprawdza, kiedy pojawi sie w wynikach
  wyszukiwarki. Przewaga[min] = T_browser - T_detect.

Zero powiadomien. Wszystko w konsoli + 4 logi w logs/:
  detect.log, compare.log, live_site.log, app.log
"""
import argparse
import asyncio
import datetime
import json
import re
import sys
import threading
import time
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from curl_cffi import requests as creq
from curl_cffi.requests import AsyncSession

IMP = "chrome124"
API = "https://www.olx.pl/api/v1/offers/"

LOG_DIR = Path(r"C:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Kategorie twarde - udowodnione sondami (probe_cat_truth.py, probe_classifier_truth.py):
#   category_id=2298 -> 100% iPhone (65/65 ofert to iPhone)
#   category_id=3102 -> 100% MacBook (65/65 to MacBook)
#   AUTA: kazda marka ma osobne category.id (BMW=183, Audi=182, Opel=198, VW=207,
#         Ford=189, Skoda=203, Toyota=206, Renault=200, Mercedes=195, Fiat=188,
#         Peugeot=199, Kia=192). Pełne auto rozpoznajemy po params (year/milage/
#         petrol/car_body/transmission), NIE po sztywnym ID.
#   czesci/akcesoria moto: 1399, 1465, 1385, 4488 i inne (maja parts_category).
IPHONE_CAT_ID = 2298
MACBOOK_CAT_ID = 3102
OTOMOTO_PARTNER = "otomoto_pl_form"

MAX_PRICE_AUTO = 12000
REGION_AUTO = "mazowieck"   # dopasowanie case-insensitive

# iPhone: akcesoria + uszkodzone/na czesci/icloud - smieci, ktorych nie szukamy
BLACKLIST_IPHONE = [
    "etui", "szkło", "szklo", "obudowa", "case", "karta sim", "karta-sim",
    "ładowarka", "ladowarka", "słuchawki", "sluchawki", "uchwyt", "folia",
    "akcesori", "pop socket", "stacjonarn",
    "icloud", "na części", "na czesci", "uszkodzony", "uszkodzona",
    "zbity", "zbita", "pęknięty", "pekniety", "pęknięta", "peknieta",
    "zalany", "zalana", "zablokowany", "zablokowana", "lock", "locked",
    "dawca", "do rozbiórki", "do rozbiorki", "do części", "do czesci",
    "do naprawy", "nie dziala", "nie działa", "martwy", "hasło", "haslo",
    "blad", "błąd", "faceid", "face id", "bezbaterii", "bez baterii",
    "slab", "słab", "bez ekranu", "uszkodzon", "popsuty", "zepsuty",
]

# MacBook: akcesoria + uszkodzone - smieci
BLACKLIST_MACBOOK = [
    "etui", "szkło", "szklo", "obudowa", "case", "ładowarka", "ladowarka",
    "słuchawki", "sluchawki", "uchwyt", "folia", "akcesori",
    "uszkodzony", "uszkodzona", "zbity", "zbita", "pęknięty", "pekniety",
    "zalany", "zalana", "zablokowany", "locked", "dawca", "na części",
    "na czesci", "do naprawy", "icloud", "hasło", "haslo",
]

# Stop-listy do wyciagania marki auta z tytulu
STOPWORDS_BRAND = {
    "sprzedam", "sprzedaż", "sprzedaz", "auto", "samochód", "samochod",
    "osobowy", "używane", "uzywane", "używany", "uzywany", "nowy", "nowe",
    "nowa", "poleasingowy", "leasing", "rocznik", "stan", "idealny",
    "bezwypadkowy", "pierwszy", "właściciel", "wlasciciel", "witam",
    "witam,", "na", "posiadam", "okazja", "zadbana",
}

_log_lock = threading.Lock()


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log_file(name, msg):
    line = f"[{_now()}] {msg}"
    try:
        print(line)
    except Exception:
        try:
            print(line.encode("ascii", "replace").decode("ascii"))
        except Exception:
            pass
    path = LOG_DIR / name
    with _log_lock:
        with open(path, "a", encoding="utf-8", errors="replace") as f:
            f.write(line + "\n")


def app_log(msg):
    log_file("app.log", msg)


def get_json(url, timeout=15):
    try:
        r = creq.get(url, impersonate=IMP, timeout=timeout)
        if r.status_code == 200:
            return r.json()
        return None
    except Exception as e:  # noqa: BLE001
        return None


def get_offer(oid):
    j = get_json(API + str(oid) + "/")
    if j is None:
        return None
    return j.get("data")


def get_list(limit=50, query=None, category_id=None, offset=0):
    url = API + f"?offset={offset}&limit={limit}"
    if query:
        url += f"&query={query}"
    if category_id:
        url += f"&category_id={category_id}"
    return get_json(url, timeout=20)


def get_max_id():
    j = get_list(50)
    if not j:
        return None
    data = j.get("data", [])
    if not data:
        return None
    return max(d["id"] for d in data)


def _price(offer):
    for p in offer.get("params", []) or []:
        if p.get("key") == "price":
            return p.get("value", {}).get("value")
    return None


def _param_keys(offer):
    return {p.get("key") for p in (offer.get("params") or [])}


def _is_full_car(offer):
    """Pełne auto osobowe, nie część/akcesorium.

    Dowód (probe_car_brands.py): pełne auta mają w params klucze
    year/milage/petrol/car_body/transmission (i często vin).
    Części moto (1465,1399,1385...) mają parts_category/part_number
    i NIE mają year+milage. Ta sygnatura odróżnia niezawodnie.
    """
    keys = _param_keys(offer)
    if "parts_category" in keys or "part_number" in keys:
        return False
    car_markers = {"year", "milage", "petrol", "car_body", "transmission", "vin"}
    return len(keys & car_markers) >= 3


def _region(offer):
    return (offer.get("location") or {}).get("region", {}).get("name") or ""


def _partner(offer):
    return (offer.get("partner") or {}).get("code") or ""


def _parse_price(value):
    """Normalizuj cene do float. Obsluguje '12000', '12 000', '12000.50', '12,000.50'."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    # usun zl, spacje, nbsp; zamien przecinek na kropke (jesli nie jest separatorem tysiecy)
    s = s.replace("zł", "").replace("zl", "").replace(" ", "").replace("\xa0", "")
    if "," in s and "." in s:
        # 12,000.50 -> 12000.50 (przecinek = tysiac, kropka = dziesietny)
        s = s.replace(",", "")
    elif "," in s:
        # 12000,50 -> 12000.50 ; 12,000 -> 12000 (ale to rzadkie, traktuj jak dziesietny)
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _pick_brand(title):
    """Wyciagnij marke/marka-model z tytulu auta; pomija stop-slowo."""
    for w in title.split():
        w_clean = re.sub(r"[^\wąćęłńóśźżĄĆĘŁŃÓŚŹŻ0-9-]", "", w.lower())
        if w_clean and w_clean not in STOPWORDS_BRAND:
            return w_clean
    return "bmw"


def _search_phrase(title, label):
    """Precyzyjna fraza do komparatora (top 50 wyszukiwarki).

    Bierzemy pierwsze 4 znaczące slowa tytulu (z marka/modelem),
    odrzucajac tylko ogolne zapychacze (sprzedam, witam, nowy...).
    Dzieki temu "iphone 14 pro max" trafia w top 50 zamiast ginać
    w 22k wynikow ogolnego "iphone".
    """
    words = []
    for w in title.split():
        w_clean = re.sub(r"[^\wąćęłńóśźżĄĆĘŁŃÓŚŹŻ0-9-]", "", w.lower())
        if w_clean and w_clean not in STOPWORDS_BRAND:
            words.append(w_clean)
        if len(words) >= 4:
            break
    return " ".join(words) if words else title.strip()


def classify(offer):
    """Zwroc (query, label) jesli oferta pasuje do twardych filtrow, inaczej None.

    Twarde kategorie (dowody):
      2298 iPhone, 3102 MacBook, 183 cale auta osobowe.
    """
    cat_id = (offer.get("category") or {}).get("id")
    title = offer.get("title") or ""
    t = title.lower()

    # iPhone: kategoria 2298 = czyste iPhone'y (dowód 65/65). NIE wymagaj
    # slowa "iphone" w tytule - oferta "Apple 14 Pro 128GB" w 2298 to tez iPhone.
    if cat_id == IPHONE_CAT_ID:
        for w in BLACKLIST_IPHONE:
            if w in t:
                return None
        return "iphone", "IPHONE"

    # MacBook: kategoria 3102, wymagany wyraz macbook/mac (nie samo "mac" jako prefix)
    if cat_id == MACBOOK_CAT_ID:
        norm = re.sub(r"\s+", "", t)  # macbookpro -> macbookpro
        if "macbook" not in t and "mac book" not in t and "macbookpro" not in norm:
            return None
        for w in BLACKLIST_MACBOOK:
            if w in t:
                return None
        return "macbook", "MACBOOK"

    # Auta: sygnatura pełnego auta (params year/milage/petrol/car_body...),
    # NIE sztywna kategoria 183 (= tylko BMW!). Kategorie marek: BMW=183,
    # Audi=182, Opel=198, VW=207, Ford=189, Skoda=203, Toyota=206...
    if (offer.get("category") or {}).get("type") == "automotive" and _is_full_car(offer):
        if _partner(offer) == OTOMOTO_PARTNER:
            return None
        if REGION_AUTO not in _region(offer).lower():
            return None
        p = _parse_price(_price(offer))
        if p is None or p > MAX_PRICE_AUTO:
            return None
        brand = _pick_brand(title)
        return brand, "AUTO"

    return None


def extract(offer, label):
    return {
        "id": offer.get("id"),
        "label": label,
        "title": (offer.get("title") or "")[:80],
        "price": _price(offer),
        "region": _region(offer),
        "city": (offer.get("location") or {}).get("city", {}).get("name"),
        "created": offer.get("created_time"),
        "partner": _partner(offer),
        "url": offer.get("url"),
    }


class Monitor:
    def __init__(self, duration_sec):
        self.duration = duration_sec
        self.stop = threading.Event()
        self.hits = {}          # id -> hit dict
        self.hits_lock = threading.Lock()
        self.visible_ids = set()  # id widziane w wyszukiwarce
        self.visible_lock = threading.Lock()
        self.compared = set()   # id juz porownane

    # ---------- T1: detektor ID (asynchroniczny, ~57 ID/s) ----------
    def detector(self):
        asyncio.run(self._detector_async())

    async def _detector_async(self):
        app_log("DETEKTOR: start (async)")
        end_time = time.time() + self.duration

        # Seed: lista top 50 jest cache'owana; znajdz prawdziwa granice 200/404.
        mx = get_max_id()
        if mx is None:
            app_log("DETEKTOR: brak seed max_id")
            return
        app_log(f"DETEKTOR: seed z listy={mx}, szukam prawdziwego max_id...")

        # Sliding window: head zawsze rowny (najwyzsze znane ID 200)+1.
        # NIGDY nie przesuwamy head o batch_size bezwarunkowo - to spowoduje
        # ucieczke w przyszłość i pomijanie ogloszen (dowód gemini + pomiar).
        head = mx - 40
        if head < 0:
            head = 0
        app_log(f"DETEKTOR: seed z listy={mx}, szukam krawedzi od {head}...")

        scanned = 0
        batch_size = 20

        # Faza 1: dojdz do krawedzi (najwyzsze istniejace 200)
        while time.time() < end_time and not self.stop.is_set():
            codes = await self._scan_batch(head, batch_size, concurrency=batch_size)
            max_seen = None
            any_200 = False
            for o, (code, _d) in sorted(codes.items()):
                scanned += 1
                if code == 200:
                    any_200 = True
                    if max_seen is None or o > max_seen:
                        max_seen = o
            if max_seen is not None:
                head = max_seen + 1
            if not any_200:
                break  # dotarlismy do krawedzi (same 404)

        app_log(f"DETEKTOR: krawedz przy oid={head}")

        # Faza 2: sliding window lapie nowe ogloszenia, nie uciekajac w przyszlosc
        while time.time() < end_time and not self.stop.is_set():
            codes = await self._scan_batch(head, batch_size, concurrency=batch_size)
            max_seen = None
            saw_network_error = False
            for o, (code, data) in sorted(codes.items()):
                scanned += 1
                if code == -1:
                    # blad sieci mimo retry - NIE przesuwaj head za ten ID
                    saw_network_error = True
                if code == 200 and data:
                    if max_seen is None or o > max_seen:
                        max_seen = o
                    res = classify(data)
                    if res:
                        query, label = res
                        hit = extract(data, label)
                        hit["query"] = query
                        hit["search"] = _search_phrase(hit["title"], label)
                        hit["t_detect"] = time.time()
                        with self.hits_lock:
                            self.hits[o] = hit
                        log_file(
                            "detect.log",
                            f"TRAFIENIE id={hit['id']} [{hit['label']}] "
                            f"cena={hit['price']} region={hit['region']} "
                            f"tytul={hit['title']} created={hit['created']}",
                        )
            if saw_network_error:
                # zostan na tym samym head, zeby powtorzyc nieudane ID
                app_log(f"DETEKTOR: blad sieci przy head={head}, retry okna")
                await asyncio.sleep(1.0)
            elif max_seen is not None:
                head = max_seen + 1
            else:
                # krawedz: same 404 -> czekaj i ponow to samo okno
                await asyncio.sleep(0.5)

            if scanned % 500 == 0:
                app_log(f"DETEKTOR: przeskanowano={scanned}, head={head}")

        app_log(f"DETEKTOR: koniec, przeskanowano={scanned}, trafienia={len(self.hits)}")

    async def _scan_batch(self, start_id, count, concurrency):
        """Skanuje statusy i od razu parsuje pelne oferty.

        Kazde ID z bledem sieci (-1) jest ponawiane do 2 razy z backoffem,
        zeby nie gubic swiezych ogloszen (dowod Gemini: 3 oferty utracone
        przez brak retry przy concurrency=20).
        """
        sem = asyncio.Semaphore(concurrency)
        results = {}

        async def fetch(session, oid):
            async with sem:
                try:
                    r = await session.get(API + str(oid) + "/")
                    if r.status_code == 200:
                        return oid, 200, r.json().get("data")
                    return oid, r.status_code, None
                except Exception:  # noqa: BLE001
                    return oid, -1, None

        async with AsyncSession(impersonate=IMP, timeout=10) as session:
            tasks = [fetch(session, start_id + i) for i in range(count)]
            gathered = await asyncio.gather(*tasks)

        for oid, code, data in gathered:
            if code != -1:
                results[oid] = (code, data)
                continue
            # retry z backoffem (maks. 2 ponowienia)
            final_code, final_data = -1, None
            for attempt in range(2):
                await asyncio.sleep(0.4 * (attempt + 1))
                try:
                    async with AsyncSession(impersonate=IMP, timeout=15) as s:
                        r = await s.get(API + str(oid) + "/")
                    if r.status_code == 200:
                        final_code, final_data = 200, r.json().get("data")
                        break
                    final_code = r.status_code
                    break
                except Exception:  # noqa: BLE001
                    final_code = -1
            results[oid] = (final_code, final_data)
        return results

    # ---------- T2: live site ----------
    def live_site(self):
        app_log("LIVE_SITE: start")
        end_time = time.time() + self.duration
        # Dowod zycia na twardych kategoriach (auta bez category_id - marki rozne)
        probes = [
            ("iphone", IPHONE_CAT_ID),
            ("macbook", MACBOOK_CAT_ID),
            ("bmw", None),
        ]
        while time.time() < end_time and not self.stop.is_set():
            for q, cid in probes:
                j = get_list(50, query=q, category_id=cid)
                if not j:
                    log_file("live_site.log", f"query={q} cat={cid} -> BRAK ODPOWIEDZI")
                    continue
                data = j.get("data", [])
                total = (j.get("metadata") or {}).get("visible_total_count")
                log_file("live_site.log", f"query={q} cat={cid} -> zwrocono={len(data)} total={total}")
                ids = {d["id"] for d in data}
                with self.visible_lock:
                    self.visible_ids.update(ids)
            time.sleep(30)

        app_log("LIVE_SITE: koniec")

    # ---------- Komparator ----------
    def comparator(self):
        app_log("KOMPARATOR: start")
        end_time = time.time() + self.duration
        while time.time() < end_time and not self.stop.is_set():
            time.sleep(20)
            with self.hits_lock:
                pending = {k: v for k, v in self.hits.items() if k not in self.compared}
            for oid, hit in list(pending.items()):
                # Komparator szuka w publicznej wyszukiwarce precyzyjna fraza
                # (hit["search"]) + twarda kategoria, i przeglada do 3 stron
                # (offset 0/50/100). Dzieki temu oferta ma szanse trafic w top.
                cat_for = {
                    "IPHONE": IPHONE_CAT_ID,
                    "MACBOOK": MACBOOK_CAT_ID,
                    "AUTO": None,  # auta: bez sztywnej kategorii (marki rozne)
                }.get(hit["label"])
                visible = False
                for off in (0, 50, 100):
                    j = get_list(50, query=hit.get("search", hit["query"]),
                                 category_id=cat_for, offset=off)
                    if not j:
                        break
                    if any(d["id"] == oid for d in j.get("data", [])):
                        visible = True
                        break
                    if len(j.get("data", [])) < 50:
                        break  # koniec wynikow, dalej nie szukaj
                if visible:
                    self.compared.add(oid)
                    t_browser = time.time()
                    przewaga_min = (t_browser - hit["t_detect"]) / 60.0
                    log_file(
                        "compare.log",
                        f"ZNALEZIONO w wyszukiwarce id={hit['id']} [{hit['label']}] "
                        f"przewaga={przewaga_min:.2f} min "
                        f"t_detect={datetime.datetime.fromtimestamp(hit['t_detect']).strftime('%H:%M:%S')} "
                        f"t_browser={datetime.datetime.fromtimestamp(t_browser).strftime('%H:%M:%S')}",
                    )

        # Podsumowanie: oferty, ktore nie pojawily sie w oknie
        with self.hits_lock:
            not_found = [h for k, h in self.hits.items() if k not in self.compared]
        for h in not_found:
            log_file(
                "compare.log",
                f"NIE_POJAWILO_SIE w oknie id={h['id']} [{h['label']}] "
                f"(detekcja wyprzedzila wyszukiwarke o cale okno)",
            )
        app_log(f"KOMPARATOR: koniec, porownano={len(self.compared)}, nie_znaleziono={len(not_found)}")

    def run(self):
        # Inicjalizuj wszystkie 4 logi - musza istniec jako dowody nawet bez trafien
        for name in ("detect.log", "compare.log", "live_site.log", "app.log"):
            path = LOG_DIR / name
            if not path.exists():
                path.write_text("", encoding="utf-8")

        app_log(f"MONITOR: start, czas_dzialania={self.duration:.0f} s")
        t1 = threading.Thread(target=self.detector, daemon=True)
        t2 = threading.Thread(target=self.live_site, daemon=True)
        t3 = threading.Thread(target=self.comparator, daemon=True)
        t1.start()
        t2.start()
        t3.start()
        t1.join()
        t2.join()
        t3.join()
        app_log("MONITOR: zakonczono")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration-min", type=float, default=20.0,
                    help="czas dzialania w minutach (domyslnie 20)")
    args = ap.parse_args()
    Monitor(args.duration_min * 60).run()