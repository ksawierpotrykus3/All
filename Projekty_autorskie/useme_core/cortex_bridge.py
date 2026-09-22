# -*- coding: utf-8 -*-
"""Reporter łańcuchów AI do Cortexa.

Każdy łańcuch zapisuje swój POSTĘP (nie mocki) do:
    cortex-app/data/pipelines/{id}/stan.json

Cortex Supervisor czyta ten plik i pokazuje kroki + statusy.

Użycie — 3 linijki na krok:

    from cortex_bridge import Chain

    chain = Chain("useme-oferty", "Wyszukiwanie ofert")

    with chain.step("Pobierz listę", typ="kod"):
        ... praca ...

    with chain.step("Wybierz oferty", typ="ai") as krok:
        krok.narzedzie = "DeepSeek"
        krok.wejscie = "dane oferty..."
        wynik = deepseek(...)
        krok.wyjscie = "wybrano 3 oferty"   # trafia do Cortexa
        krok.reasoning = "uzasadnienie..."

    with chain.step("Akceptacja", typ="warunek") as krok:
        krok.czekaj_na_ciebie()              # bramka — czeka na człowieka

Statusy są wyłącznie realne:
    w_toku -> zrobione  (sukces)
    w_toku -> blad      (wyjątek)
    czeka_na_ciebie     (jawnie ustawiony punkt kontrolny)

Zero aliasów, zero mapowań, zero domyślnych fałszywych statusów.
"""

from __future__ import annotations

import atexit
import json
import sys
import time
import traceback
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional

from storage import atomic_write_json

_cortex_candidate = Path(__file__).resolve().parent.parent / "cortex-app" / "data" / "pipelines"
if _cortex_candidate.parent.parent.exists():
    PIPELINES_DIR = _cortex_candidate
else:
    PIPELINES_DIR = Path(__file__).resolve().parent / "data" / "pipelines"

# Minimalny odstep miedzy zapisami stanu podczas streamu (sekundy).
_STREAM_SAVE_INTERVAL = 0.5

_ACTIVE_CHAINS: List[Chain] = []


def _atexit_panic_handler():
    """Zabezpieczenie przed wiszącym w_toku przy nagłym zakończeniu procesu."""
    for chain in list(_ACTIVE_CHAINS):
        modified = False
        for krok in chain.kroki:
            if krok.status == "w_toku":
                krok.status = "blad"
                krok.log("[PANIC] Proces Pythona został nagle przerwany lub zakończony.")
                if not krok.wyjscie:
                    krok.wyjscie = "AWARYJNE PRZERWANIE PROCESU"
                modified = True
        if modified:
            chain._zapisz()


def _excepthook_panic_handler(exc_type, exc_value, exc_traceback):
    """Przechwytuje każdy nieobsłużony błąd i raportuje go wprost do stanu Cortexa."""
    tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    for chain in list(_ACTIVE_CHAINS):
        modified = False
        for krok in chain.kroki:
            if krok.status == "w_toku":
                krok.status = "blad"
                krok.log(f"[KATASTROFA] {exc_type.__name__}: {exc_value}")
                krok.log(f"Stacktrace:\n{tb_text[-1200:]}")
                if not krok.wyjscie:
                    krok.wyjscie = f"JEBŁO: {exc_type.__name__}: {exc_value}"
                modified = True
        if modified:
            chain._zapisz()
    _orig_excepthook(exc_type, exc_value, exc_traceback)


_orig_excepthook = sys.excepthook
sys.excepthook = _excepthook_panic_handler
atexit.register(_atexit_panic_handler)


class Krok:
    def __init__(self, nazwa: str, typ: str, opis: str = "", on_update: Optional[Callable[[], None]] = None):
        self.nazwa = nazwa
        self.typ = typ
        self.opis = opis
        self.status = "w_toku"
        self._start = time.time()
        self._on_update = on_update
        self.narzedzie: Optional[str] = None
        self.wejscie: Optional[str] = None
        self.promptSystem: Optional[str] = None
        self.promptUser: Optional[str] = None
        self.wyjscie: Optional[str] = None
        self._wyjscie_chunks: List[str] = []
        self.reasoning: Optional[str] = None
        self.logi: List[str] = []

    def czekaj_na_ciebie(self) -> None:
        self.status = "czeka_na_ciebie"
        self._notify()

    def log(self, wiadomosc: str) -> None:
        self.logi.append(wiadomosc)
        self._notify()

    def stream(self, fragment: str) -> None:
        """Dokleja fragment wyniku AI i okresowo zapisuje stan (podglad na zywo).

        Throttling: zapis na dysk max raz na _STREAM_SAVE_INTERVAL sekund, bo
        zapis calego stan.json (z promptami i researchem) przy kazdym fragmencie
        streamu zamulal proces przy duzych zleceniach.
        """
        self._wyjscie_chunks.append(fragment)
        self.wyjscie = "".join(self._wyjscie_chunks)
        now = time.time()
        if now - getattr(self, "_last_stream_save", 0.0) >= _STREAM_SAVE_INTERVAL:
            self._last_stream_save = now
            self._notify()

    def finalizuj_wynik(self, tresc: str) -> None:
        """Ustawia pełny, końcowy wynik (nadpisuje stream)."""
        self.wyjscie = tresc
        self._notify()

    def _notify(self) -> None:
        if self._on_update:
            self._on_update()

    def to_dict(self, index: int) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "id": index,
            "nazwa": self.nazwa,
            "typ": self.typ,
            "status": self.status,
        }
        if self.opis:
            d["opis"] = self.opis
        if self.narzedzie:
            d["narzedzie"] = self.narzedzie
        if self.wejscie:
            d["wejscie"] = self.wejscie
        if self.promptSystem:
            d["promptSystem"] = self.promptSystem
        if self.promptUser:
            d["promptUser"] = self.promptUser
        if self.wyjscie:
            d["wyjscie"] = self.wyjscie
        if self.reasoning:
            d["reasoning"] = self.reasoning
        if self.logi:
            d["logi"] = self.logi
        d["czas_trwania_s"] = round(time.time() - self._start, 1)
        return d


class Chain:
    def __init__(self, id: str, nazwa: str, katalog: Optional[Path] = None,
                 opis: str = "", silnik: str = "", wyzwalacz: str = "manual",
                 parent_id: Optional[str] = None, parent_step: Optional[str] = None):
        self.id = id
        self.nazwa = nazwa
        self.opis = opis
        self.silnik = silnik
        self.wyzwalacz = wyzwalacz
        self.parent_id = parent_id
        self.parent_step = parent_step
        self.kroki: List[Krok] = []
        self.katalog = katalog or PIPELINES_DIR
        _ACTIVE_CHAINS.append(self)
        self._zapisz()

    def _zapisz_now(self) -> None:
        self._zapisz()

    @contextmanager
    def step(self, nazwa: str, typ: str = "ai", opis: str = "") -> Iterator[Krok]:
        krok = Krok(nazwa, typ, opis, on_update=self._zapisz_now)
        self.kroki.append(krok)
        self._zapisz()
        try:
            yield krok
        except Exception as e:
            krok.status = "blad"
            krok.log(f"[BŁĄD KROKU] {type(e).__name__}: {e}")
            if not krok.wyjscie:
                krok.wyjscie = f"BŁĄD: {type(e).__name__}: {e}"
            self._zapisz()
            raise
        else:
            # Nadpisz na zrobione tylko jeśli nikt nie ustawił bramki.
            if krok.status == "w_toku":
                krok.status = "zrobione"
            self._zapisz()

    def _status_ogolny(self) -> str:
        if not self.kroki:
            return "oczekuje"
        statusy = [k.status for k in self.kroki]
        if "blad" in statusy:
            return "blad"
        if "w_toku" in statusy:
            return "w_toku"
        if "czeka_na_ciebie" in statusy:
            return "czeka_na_ciebie"
        if all(s == "zrobione" for s in statusy):
            return "zakonczono"
        return "oczekuje"

    def _to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "id": self.id,
            "nazwa": self.nazwa,
            "kroki": [k.to_dict(i + 1) for i, k in enumerate(self.kroki)],
            "status_ogolny": self._status_ogolny(),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        if self.opis:
            d["opis"] = self.opis
        if self.silnik:
            d["silnik"] = self.silnik
        if self.parent_id:
            d["parent_id"] = self.parent_id
        if self.parent_step:
            d["parent_step"] = self.parent_step
        if self.wyzwalacz:
            d["wyzwalacz"] = self.wyzwalacz
            d["wyzwalacz_typ"] = self.wyzwalacz
        return d

    def _zapisz(self) -> None:
        podkatalog = self.katalog / self.id
        podkatalog.mkdir(parents=True, exist_ok=True)
        plik = podkatalog / "stan.json"
        atomic_write_json(plik, self._to_dict())