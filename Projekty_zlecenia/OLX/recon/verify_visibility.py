# coding: utf-8
"""
Weryfikacja widocznosci ofert z detect.log w wyszukiwarce OLX.

Dla kazdego trafienia:
  1) pobiera oferte /offers/{id}/ (prawda o ofercie),
  2) wyszukuje ja w wyszukiwarce (query=fraza z tytulu, limit=50),
  3) sprawdza, czy ID jest w wynikach.

Dowodzi, czy "NIE_POJAWILO_SIE" byl prawda, czy artefaktem
zbyt ogolnego zapytania (iphone/macbook/bmw) w komparatorze.
"""
import re
from pathlib import Path
from curl_cffi import requests as creq

IMP = "chrome124"
API = "https://www.olx.pl/api/v1/offers/"
LOG_DIR = Path(r"C:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\logs")


def get_json(url, timeout=20):
    try:
        r = creq.get(url, impersonate=IMP, timeout=timeout)
        return r.status_code, (r.json() if r.status_code == 200 else None)
    except Exception as e:  # noqa: BLE001
        return -1, str(e)


def parse_detect_ids(limit=12):
    ids = []
    for line in (LOG_DIR / "detect.log").read_text(encoding="utf-8").splitlines():
        m = re.search(r"id=(\d+)", line)
        if m:
            ids.append(int(m.group(1)))
    return ids[:limit]


def search_query(frag):
    code, j = get_json(API + f"?offset=0&limit=50&query={frag}")
    if code != 200 or not j:
        return code, []
    return 200, [d["id"] for d in j.get("data", [])]


def main():
    ids = parse_detect_ids()
    print(f"Sprawdzam {len(ids)} ID z detect.log\n")
    for oid in ids:
        code, j = get_json(API + str(oid) + "/")
        if code != 200 or not j:
            print(f"id={oid} brak oferty (code={code})")
            continue
        offer = j.get("data", {})
        title = offer.get("title") or ""
        words = [w for w in re.findall(r"[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ0-9]+", title.lower())]
        frag = words[0] if words else title
        sc, found_ids = search_query(frag)
        visible = oid in found_ids
        print(f"id={oid} | {title[:45]!r}")
        print(f"   query={frag!r} -> status={sc}, zwrocono={len(found_ids)}, widoczne={visible}")
        if visible:
            print(f"   >>> FAKT: oferta JEST w wyszukiwarce (komparator tego nie widzial)")
        else:
            print(f"   >>> nie w top 50 wynikow tego zapytania")
        print()


if __name__ == "__main__":
    main()