# -*- coding: utf-8 -*-
"""Deterministyczny kalkulator wyceny.

Model (agent 02b) zwraca STRUKTURE (moduly, godziny, flagi), a ten modul liczy
kwote i dni wg mechanika_wyceniania.md. Ta sama struktura = zawsze ta sama cena.

Funkcja publiczna:
    policz_wycene(dane: dict) -> dict
Zwraca dict z: kwota, dni, typ, rozbicie, ostrzezenia.
"""
from __future__ import annotations

import math
import random
import re
from typing import Any, Dict, List, Optional


# --- Parametry mechaniki (twarde) ---
STAWKA_EFEKTYWNA = 90          # zl/h (srodek pasma; profil 2 mies., 5 umow)
STAWKA_MIN = 82                # dolna granica losowania (nigdy za nisko)
STAWKA_MAX = 110               # gorna granica losowania (nigdy za wysoko)
NARZUT_TESTY = 0.15            # +15% testy/dokumentacja
BUFOR_STANDARD = 0.20          # +20%
BUFOR_NOWA_TECH = 0.30         # +30% tylko dla niszowej nowej technologii
CAP_MNOZNIKOW = 1.8
MIN_KWOTA = 500
MIN_DNI = 7
MIN_STAWKA_GODZINOWA = 80      # sanity-check: efektywna stawka nie moze spasc ponizej (zl/h)
DNI_STOPA = 7                  # h/dzien
DNI_WEEKEND = 1.30             # +30% na weekendy i komunikacje

# Reguly korekty konkurencyjnej (KROK 7) - domkniete przedzialy
# (wiek_min, wiek_max, ofert_min, ofert_max, mnoznik)
KOREKTY = [
    (0, 1, 20, None, 0.9),     # swieze do 24h, >=20 ofert
    (0, 1, 0, 20, 1.0),        # swieze do 24h, <20
    (1, 3, 20, None, 0.9),     # 1-3 dni, >=20
    (1, 3, 0, 20, 1.0),        # 1-3 dni, <20
    (3, None, 0, 10, 1.15),    # >3 dni, <10
    (3, None, 10, 30, 0.95),   # >3 dni, 10-30
    (3, None, 30, None, 0.85), # >3 dni, >30
]

# Widełki retainerowe
RETAINER_WIDEŁKI = {"opieka_techniczna": (1500, 2500),
                    "customer_success": (2500, 5000)}

# Twardy cap godzin dla One-Page (kontrakt z uzytkownikiem)
CAP_ONE_PAGE_H = 25

# Maksymalny rozrzut stawki miedzy ofertami na TO SAMO zlecenie (zl/h).
# Baza stawki jest wspolna dla zlecenia, a kazda oferta dostaje maly offset
# w zakresie -STAWKA_OFFSET_MAX..+STAWKA_OFFSET_MAX. Dzieki temu oferty na to samo
# zlecenie nie sa diametralnie rozne (max roznica = 2 * STAWKA_OFFSET_MAX).
STAWKA_OFFSET_MAX = 6


def wylosuj_stawke(seed: Optional[str] = None) -> int:
    """Losuje stawke efektywna (zl/h) w bezpiecznym pasmie STAWKA_MIN..STAWKA_MAX.

    - Nigdy nie schodzi ponizej STAWKA_MIN (za nisko) ani nie przekracza STAWKA_MAX (za wysoko).
    - Ten sam seed -> ta sama stawka (deterministycznie, odporne na retry).
    - Bez seeda losuje za kazdym razem.
    """
    if seed is not None:
        rnd = random.Random(str(seed))
        return rnd.randint(STAWKA_MIN, STAWKA_MAX)
    return random.randint(STAWKA_MIN, STAWKA_MAX)


def stawka_dla_oferty(job_id: Optional[str], offer_seed: Optional[str]) -> int:
    """Liczy stawke dla KONKRETNEJ oferty na podstawie wspolnej bazy zlecenia + malego offsetu.

    - Baza: losowana raz per ZLECENIE (deterministycznie po job_id) w [STAWKA_MIN, STAWKA_MAX].
    - Offset: maly, per OFERTA (po offer_seed), w [-STAWKA_OFFSET_MAX, +STAWKA_OFFSET_MAX].
    - Wynik przyciety do [STAWKA_MIN, STAWKA_MAX].

    Efekt: dwie oferty na to samo zlecenie maja stawki blisko siebie
    (max roznica 2*STAWKA_OFFSET_MAX), a nie diametralnie rozne.
    """
    if job_id:
        baza = wylosuj_stawke(job_id)
    else:
        baza = STAWKA_EFEKTYWNA
    if offer_seed:
        rnd = random.Random(str(offer_seed))
        offset = rnd.randint(-STAWKA_OFFSET_MAX, STAWKA_OFFSET_MAX)
    else:
        offset = 0
    return max(STAWKA_MIN, min(STAWKA_MAX, baza + offset))


def _safe_int(value: Any, default: int = 0) -> int:
    """Bezpieczne parsowanie liczby calkowitej. Toleruje '6 dni temu', '37 ofert'."""
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    m = re.search(r"\d+", str(value))
    return int(m.group(0)) if m else default


def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """Bezpieczne parsowanie liczby zmiennoprzecinkowej z dowolnego tekstu.

    Toleruje '12 000 zl', '12000', 'do negocjacji' (-> default)."""
    if value is None:
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    txt = str(value).replace("\xa0", "").replace(" ", "")
    m = re.search(r"\d+(?:[.,]\d+)?", txt)
    if not m:
        return default
    try:
        return float(m.group(0).replace(",", "."))
    except ValueError:
        return default


def _korekta_konkurencyjna(wiek: int, ofert: int) -> float:
    """Zwraca mnoznik korekty konkurencyjnej wg KROK 7."""
    for w_min, w_max, o_min, o_max, mnoz in KOREKTY:
        w_ok = (wiek >= w_min) and (w_max is None or wiek < w_max)
        o_ok = (ofert >= o_min) and (o_max is None or ofert <= o_max)
        if w_ok and o_ok:
            return mnoz
    return 1.0


def _zaokraglij(kwota: float) -> int:
    """KROK 9: zaokraglenie wg przedzialu."""
    if kwota <= 2000:
        return int(round(kwota / 50.0) * 50)
    if kwota <= 10000:
        return int(round(kwota / 500.0) * 500)
    return int(round(kwota / 1000.0) * 1000)


def policz_wycene(dane: Dict[str, Any]) -> Dict[str, Any]:
    """Liczy wycene deterministycznie z struktury zwroconej przez model."""
    flagi = dane.get("flagi", {}) or {}
    typ = (dane.get("typ_zlecenia") or "projekt").lower()
    ostrzezenia: List[str] = []
    rozbicie: Dict[str, Any] = {}

    wiek = _safe_int(flagi.get("wiek_ofert_dni"), 0)
    ofert = _safe_int(flagi.get("liczba_ofert"), 0)

    # Stawka efektywna: DETERMINISTYCZNA, z profilu wykonawcy.
    # - Profil "2 mies., 5 umow" -> mnoznik ×0.75 od bazy 120 zl/h = 90 zl/h.
    # - Model NIE moze nadpisac stawki (pole "stawka" w JSON jest ignorowane).
    # - Usunieto losowanie 82-110 zl/h oraz honorowanie dane["stawka"], ktore
    #   powodowaly rozrzut 86/92/96/100/110 w roznych ofertach (patrz walidator 08).
    stawka = STAWKA_EFEKTYWNA  # 90 zl/h, deterministyczna z profilu

    # --- Male zlecenia: tabela rynkowa ---
    if typ in ("male", "małe"):
        kwota = _safe_float(dane.get("kwota_rynek"), MIN_KWOTA) or MIN_KWOTA
        kwota = max(kwota, MIN_KWOTA)
        dni = MIN_DNI
        return {
            "typ": "male",
            "kwota": int(kwota),
            "dni": dni,
            "rozbicie": {"tryb": "tabela rynkowa", "kwota_rynek": kwota},
            "ostrzezenia": ostrzezenia,
        }

    # --- Retainer ---
    if typ == "retainer":
        stawka = _safe_float(dane.get("retainer_stawka_mies"), 0.0) or 0.0
        if stawka <= 0:
            ostrzezenia.append("retainer bez stawki - uzyto dolnej granicy opieki")
            stawka = RETAINER_WIDEŁKI["opieka_techniczna"][0]
        # mnozniki ryzyka dla retainera
        m = 1.0
        if flagi.get("brak_specyfikacji"):
            m *= 1.3
        if flagi.get("ograniczenia_api"):
            m *= 1.25
        m = min(m, CAP_MNOZNIKOW)
        stawka_po = stawka * m
        korekta = _korekta_konkurencyjna(wiek, ofert)
        stawka_po *= korekta
        stawka_konc = int(round(stawka_po / 100.0) * 100)
        return {
            "typ": "retainer",
            "kwota": stawka_konc,
            "dni": MIN_DNI,
            "okres": "miesiecznie",
            "rozbicie": {"tryb": "retainer", "okres": "miesiecznie",
                         "stawka_bazowa": stawka,
                         "mnoznik": round(m, 3), "korekta": korekta},
            "ostrzezenia": ostrzezenia,
        }

    # --- Projekt godzinowy ---
    moduly = dane.get("moduly") or []
    if not moduly:
        ostrzezenia.append("brak modulow - uzyto minimum")
        godziny_real = 1.0
    else:
        godziny_real = sum(_safe_float(m.get("godziny_real"), 0.0) or 0.0 for m in moduly)

    # Kontrakt: One-Page ma twardy cap 25h, ale TYLKO gdy zlecenie JEST landingiem.
    # Gdy landing jest jednym z wielu modułów (np. aplikacja mobilna + panel + landing),
    # NIE przycinamy calego zlecenia - inaczej duzy projekt zostanie wyceniony jak landing.
    def _is_landing(n: str) -> bool:
        return ("one-page" in n) or ("landing" in n)
    moduly_landing = [m for m in moduly if _is_landing((m.get("nazwa") or "").lower())]
    moduly_inne = [m for m in moduly if not _is_landing((m.get("nazwa") or "").lower())]
    # "Czysty landing" = sa moduly landingowe i NIC poza nimi (sam landing, max 1-2 moduly).
    czysty_landing = bool(moduly_landing) and not moduly_inne
    if czysty_landing:
        if godziny_real > CAP_ONE_PAGE_H:
            ostrzezenia.append(
                f"One-Page: cap {CAP_ONE_PAGE_H}h (bylo {godziny_real}h) - przycieto")
            godziny_real = CAP_ONE_PAGE_H
    elif moduly_landing:
        # Landing jest czescia wiekszego projektu - przycinamy TYLKO modul landing,
        # jesli sam przekracza cap. Reszta modulow bez zmian.
        do_cap = 0.0
        for m in moduly_landing:
            h = _safe_float(m.get("godziny_real"), 0.0) or 0.0
            if h > CAP_ONE_PAGE_H:
                ostrzezenia.append(
                    f"Modul landing: cap {CAP_ONE_PAGE_H}h (bylo {h}h) - przycieto sam modul")
                do_cap += h - CAP_ONE_PAGE_H
        if do_cap:
            godziny_real -= do_cap

    # KROK 2.5 testy/dokumentacja
    po_testach = godziny_real * (1 + NARZUT_TESTY)

    # KROK 4 buffer
    if flagi.get("nowa_technologia"):
        bufor = BUFOR_NOWA_TECH
    else:
        bufor = BUFOR_STANDARD
    po_buforze = po_testach * (1 + bufor)

    # KROK 5 mnozniki ryzyka
    mnoznik = 1.0
    ma_figme = bool(flagi.get("figma_w_ogloszeniu"))
    if ma_figme:
        # Klient ma Figme + specyfikacje -> mniej niewiadomych (×0.9),
        # zamiast kary za brak specyfikacji.
        mnoznik *= 0.9
    elif flagi.get("brak_specyfikacji"):
        mnoznik *= 1.3
    if flagi.get("ograniczenia_api"):
        mnoznik *= 1.25
    if flagi.get("real_time"):
        mnoznik *= 1.2
    mnoznik = min(mnoznik, CAP_MNOZNIKOW)
    po_mnoznikach = po_buforze * mnoznik

    # KROK 6 cena bazowa
    cena_bazowa = po_mnoznikach * stawka

    # KROK 7 korekta konkurencyjna
    korekta = _korekta_konkurencyjna(wiek, ofert)
    cena_po_korekcie = cena_bazowa * korekta

    # KROK 9.5 budzet jawny (podnies do 80-90% budzetu jesli wyzszy, ale z capem na szok cenowy)
    budzet = flagi.get("budzet_jawny")
    if budzet:
        budzet_val = _safe_float(budzet, None)
        if budzet_val and budzet_val > cena_po_korekcie:
            # Ochrona przed szokiem cenowym (klient podaje budzet 50k, kalkulacja 3k):
            # Nie pozwalamy na skok wyzszy niz 1.4x wyliczonej ceny bazowej
            target = budzet_val * 0.85
            cena_po_korekcie = min(target, cena_po_korekcie * 1.4)
            ostrzezenia.append(f"korekta budzetowa (85% budzetu z capem 1.4x): {cena_po_korekcie:.0f} zl")

    # KROK 9 zaokraglenie
    kwota = max(_zaokraglij(cena_po_korekcie), MIN_KWOTA)

    # --- SANITY-CHECK: efektywna stawka za godzine nie moze byc podejrzanie niska ---
    # Lapie sytuacje, gdy korekta/cap zanizyly kwote o rzad wielkosci
    # (np. duzy projekt przyciety do capu landingu).
    sanity_ok = True
    efektywna_stawka = (kwota / godziny_real) if godziny_real > 0 else kwota
    if efektywna_stawka < MIN_STAWKA_GODZINOWA:
        sanity_ok = False
        ostrzezenia.append(
            f"SANITY: efektywna stawka {efektywna_stawka:.1f} zl/h < progu {MIN_STAWKA_GODZINOWA} zl/h "
            f"({godziny_real:.0f}h, kwota {kwota}) - wycena podejrzanie niska!"
        )

    # KROK 10 dni
    dni = math.ceil(po_mnoznikach / DNI_STOPA)
    dni = math.ceil(dni * DNI_WEEKEND)
    dni = max(dni, MIN_DNI)

    rozbicie = {
        "tryb": "projekt",
        "moduly": moduly,
        "godziny_real": round(godziny_real, 1),
        "po_testach_15": round(po_testach, 1),
        "bufor": bufor,
        "po_buforze": round(po_buforze, 1),
        "mnoznik_ryzyka": round(mnoznik, 3),
        "cap_zadzialal": mnoznik >= CAP_MNOZNIKOW,
        "po_mnoznikach": round(po_mnoznikach, 1),
        "stawka": stawka,
        "cena_bazowa": round(cena_bazowa, 1),
        "korekta_konkurencyjna": korekta,
        "cena_po_korekcie": round(cena_po_korekcie, 1),
        "kwota_koncowa": kwota,
        "efektywna_stawka": round(efektywna_stawka, 1),
        "sanity_ok": sanity_ok,
    }
    return {"typ": "projekt", "kwota": kwota, "dni": dni,
            "rozbicie": rozbicie, "ostrzezenia": ostrzezenia,
            "sanity_ok": sanity_ok}


def formatuj_wynik(wynik: Dict[str, Any]) -> str:
    """Zwraca blok [WYNIK_KONCOWY] + krotkie rozbicie do wklejenia."""
    linie = []
    linie.append("[WYNIK_KONCOWY]")
    linie.append(f"KWOTA: {wynik['kwota']}")
    linie.append(f"DNI: {wynik['dni']}")
    if wynik.get("typ") == "retainer" or wynik.get("okres"):
        linie.append("OKRES: miesiecznie (stala wspolpraca, nie kwota jednorazowa)")
    linie.append("[/WYNIK_KONCOWY]")
    return "\n".join(linie)


if __name__ == "__main__":
    import sys, json
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    przyklad = {
        "typ_zlecenia": "projekt",
        "moduly": [{"nazwa": "Landing page / One-Page", "godziny_real": 20}],
        "flagi": {"brak_specyfikacji": True, "wiek_ofert_dni": 1,
                  "liczba_ofert": 71, "nowa_technologia": False},
    }
    w = policz_wycene(przyklad)
    print(json.dumps(w, ensure_ascii=False, indent=2))