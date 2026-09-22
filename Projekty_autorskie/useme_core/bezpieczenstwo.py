# -*- coding: utf-8 -*-
"""Bezpieczeństwo operacyjne: kill switch, limity dzienne, okno czasowe runu.

Moduł trzyma stan licznika dziennego w magazyn/.bezpieczenstwo.json i udostępnia:
- czy_stop(): czy istnieje plik STOP (kill switch).
- zapisz_wyslana_oferte(): inkrementuje licznik dzienny (statystyka, nie limit).
- RunLimiter: pilnuje czasu jednego uruchomienia (MAX_RUN_MINUTES).

Zero zależności od AI/przeglądarki - czysty Python, łatwo testować.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import config

STAN_FILE = config.MAGAZYN_DIR / ".bezpieczenstwo.json"


def _dzis() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _wczytaj_stan() -> dict:
    if STAN_FILE.exists():
        try:
            return json.loads(STAN_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _zapisz_stan(stan: dict) -> None:
    STAN_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STAN_FILE.parent / f".tmp_{STAN_FILE.name}_{time.time_ns()}"
    tmp.write_text(json.dumps(stan, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STAN_FILE)


def czy_stop() -> bool:
    """Kill switch: jeśli istnieje plik STOP, bot ma się nie uruchamiać / zatrzymać."""
    return config.STOP_FILE.exists()


def pobierz_licznik_dzienny() -> int:
    """Zwraca liczbę ofert wysłanych dzisiaj (wszystkie konta razem)."""
    stan = _wczytaj_stan()
    if stan.get("data") != _dzis():
        return 0
    return int(stan.get("wyslane_dzis", 0))





def zapisz_wyslana_oferte() -> int:
    """Inkrementuje dzienny licznik wysłanych ofert. Zwraca nową wartość."""
    stan = _wczytaj_stan()
    if stan.get("data") != _dzis():
        stan = {"data": _dzis(), "wyslane_dzis": 0}
    stan["wyslane_dzis"] = int(stan.get("wyslane_dzis", 0)) + 1
    stan["ostatnia_aktualizacja"] = datetime.now().isoformat()
    _zapisz_stan(stan)
    return stan["wyslane_dzis"]


class RunLimiter:
    """Pilnuje maksymalnego czasu jednego uruchomienia pipeline'u."""

    def __init__(self, max_minutes: Optional[int] = None):
        self.max_seconds = (max_minutes or config.MAX_RUN_MINUTES) * 60
        self.start = time.time()

    def przekroczono(self) -> bool:
        return (time.time() - self.start) > self.max_seconds

    def pozostalo_s(self) -> float:
        return max(0.0, self.max_seconds - (time.time() - self.start))