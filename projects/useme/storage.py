# -*- coding: utf-8 -*-
"""Magazyn ofert (Storage & Deduplication).

Zarządza bazą pobranych zleceń w useme_core/magazyn/:
- deduplikacja: sprawdza czy zlecenie o danym ID/URL już istnieje,
- zapisywanie surowych danych i pełnych detali,
- aktualizacja statusu: NOWA -> WYBRANA_AI -> PRZYGOTOWANA -> WYSLANO (lub DRY_RUN_OK).
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).parent
MAGAZYN_DIR = BASE_DIR / "magazyn"
CHECKPOINTS_DIR = MAGAZYN_DIR / ".checkpoints"
MARKER_FILE = BASE_DIR / "marker.json"


def atomic_write_json(path: Path | str, data: Any, indent: int = 2) -> None:
    """Zapisuje dane do pliku w sposób atomowy (plik .tmp + os.replace).

    Chroni przed uszkodzeniem lub wyzerowaniem pliku (0 KB) w przypadku
    awarii zasilania, błędu procesu lub wymuszonego zatrzymania w trakcie zapisu.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    temp_file = p.parent / f".tmp_{p.name}_{os.getpid()}_{time.time_ns()}"
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        for attempt in range(5):
            try:
                temp_file.replace(p)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.05 * (attempt + 1))
    except Exception:
        if temp_file.exists():
            try:
                temp_file.unlink()
            except OSError:
                pass
        raise


class Storage:
    def __init__(self, magazyn_dir: Optional[Path] = None):
        self.magazyn_dir = magazyn_dir or MAGAZYN_DIR
        self.magazyn_dir.mkdir(parents=True, exist_ok=True)

    def _get_category_slug(self, category_url_or_name: str) -> str:
        """Normalizuje nazwę kategorii do folderu."""
        if "serwisy" in category_url_or_name.lower():
            return "serwisy-internetowe"
        return "programowanie-i-it"

    def exists(self, job_id: str, category: str = "programowanie-i-it") -> bool:
        """Sprawdza deterministycznie czy oferta już jest w magazynie."""
        job_id = str(job_id).strip()
        slug = self._get_category_slug(category)
        job_file = self.magazyn_dir / slug / f"{job_id}.json"
        if job_file.exists():
            return True
        for path in self.magazyn_dir.glob(f"*/{job_id}.json"):
            return True
        return False

    def save_new_job(self, job_data: Dict[str, Any], category: str = "programowanie-i-it") -> Path:
        """Zapisuje nowo wykryte zlecenie z listy."""
        job_id = str(job_data.get("id", "")).strip()
        if not job_id:
            raise ValueError("Brak pola 'id' w danych zlecenia!")

        slug = self._get_category_slug(category)
        cat_dir = self.magazyn_dir / slug
        cat_dir.mkdir(parents=True, exist_ok=True)

        job_file = cat_dir / f"{job_id}.json"
        
        record = {
            "id": job_id,
            "url": job_data.get("url", ""),
            "title": job_data.get("title", ""),
            "author": job_data.get("author", ""),
            "author_id": job_data.get("author_id", ""),
            "budget": job_data.get("budget", ""),
            "category": slug,
            "detected_at": datetime.now().isoformat(),
            "status": "NOWA",
            "list_details": job_data,
            "full_details": None,
            "ai_proposal": None,
            "submission_result": None
        }

        atomic_write_json(job_file, record)
        self._update_marker(job_id, job_data.get("url", ""))
        return job_file

    def update_job(self, job_id: str, updates: Dict[str, Any], category: str = "programowanie-i-it") -> None:
        """Aktualizuje istniejący rekord zlecenia w magazynie (zapis atomowy)."""
        job_id = str(job_id).strip()
        target_file = None
        for path in self.magazyn_dir.glob(f"*/{job_id}.json"):
            target_file = path
            break

        if not target_file:
            slug = self._get_category_slug(category)
            target_file = self.magazyn_dir / slug / f"{job_id}.json"
            record = {"id": job_id, "status": "NOWA"}
        else:
            with open(target_file, "r", encoding="utf-8") as f:
                record = json.load(f)

        record.update(updates)
        record["updated_at"] = datetime.now().isoformat()

        atomic_write_json(target_file, record)

    def load_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Odczytuje zlecenie po ID."""
        job_id = str(job_id).strip()
        for path in self.magazyn_dir.glob(f"*/{job_id}.json"):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def zapisz_oferte(self, job_id: str, oferta: Dict[str, Any],
                      category: str = "programowanie-i-it") -> None:
        """Dopisuje ofertę do listy 'oferty' w rekordzie zlecenia.

        Kazda oferta to osobny wpis z pelnym kontekstem eksperymentu:
        konto, tryb (konserwatywny), adres wariantu, seed, stawka, kwota,
        dni, dlugosc tresci. Dzieki temu po powrocie wiadomo DOKLADNIE co,
        z jakiego konta i w jakim trybie zostalo wyslane.
        """
        job_id = str(job_id).strip()
        target_file = None
        for path in self.magazyn_dir.glob(f"*/{job_id}.json"):
            target_file = path
            break

        if not target_file:
            slug = self._get_category_slug(category)
            target_file = self.magazyn_dir / slug / f"{job_id}.json"
            record = {"id": job_id, "status": "NOWA", "oferty": []}
        else:
            with open(target_file, "r", encoding="utf-8") as f:
                record = json.load(f)

        oferty = record.get("oferty")
        if not isinstance(oferty, list):
            oferty = []
        wpis = dict(oferta)
        wpis["zapisano_at"] = datetime.now().isoformat()
        oferty.append(wpis)
        record["oferty"] = oferty
        record["updated_at"] = datetime.now().isoformat()

        atomic_write_json(target_file, record)

    def find_by_account(self, konto_id: str) -> list:
        """Zwraca wszystkie zlecenia, na ktore dane konto zlozylo oferte.

        Sluzy do anty-powtorki per konto (co juz wyslalismy z tego konta),
        niezaleznie od tego, ze zlecenie obsluguje tez drugie konto.
        """
        results: list = []
        if not konto_id:
            return results
        target = str(konto_id).strip().lower()
        for path in self.magazyn_dir.rglob("*.json"):
            if path.name in {"marker.json"} or path.name.startswith("_"):
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            for o in (data.get("oferty") or []):
                if str(o.get("konto", "")).strip().lower() == target:
                    data["_path"] = str(path)
                    results.append(data)
                    break
        return results

    def czy_konto_juz_oferowalo(self, job_id: str, konto_id: str) -> bool:
        """Sprawdza, czy dane konto zlozylo juz oferte na to zlecenie.

        Deduplikacja per konto: konto1 moze zlozyc oferte, a konto2 nadal
        moze zlozyc swoja wlasna na to samo zlecenie.
        """
        job = self.load_job(job_id)
        if not job:
            return False
        target = str(konto_id).strip().lower()
        for o in (job.get("oferty") or []):
            if str(o.get("konto", "")).strip().lower() == target:
                st = str(o.get("status") or job.get("status") or "").upper()
                if st in ("WYSLANO", "DRY_RUN_OK", "ZLOZONO"):
                    return True
                if st in ("AUTH_REQUIRED", "PRZYGOTOWANA", "BLAD_FORMULARZA", "NOWA", "POBRANO_DETALE", "BLAD_PRZETWARZANIA"):
                    continue
                return True
        return False

    def wszystkie_oferty(self, limit_dni: Optional[int] = None) -> list:
        """Zwraca plaska liste wszystkich ofert ze wszystkich zlecen.

        Uzywane przez globalny wykrywacz duplikatow. Kazdy wpis wzbogacony
        o job_id. Opcjonalnie tylko z ostatnich N dni.
        """
        from datetime import timedelta
        granica = None
        if limit_dni is not None:
            granica = datetime.now() - timedelta(days=limit_dni)
        wyniki: list = []
        for path in self.magazyn_dir.rglob("*.json"):
            if path.name in {"marker.json"} or path.name.startswith("_"):
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            for o in (data.get("oferty") or []):
                if granica is not None:
                    try:
                        ts = datetime.fromisoformat(str(o.get("zapisano_at", "")))
                        if ts < granica:
                            continue
                    except Exception:
                        pass
                wpis = dict(o)
                wpis["job_id"] = data.get("id")
                wyniki.append(wpis)
        return wyniki

    def find_by_author(self, author_id: str) -> list:
        """Zwraca wszystkie zlecenia z magazynu, które pochodzą od danego autora.

        author_id to stabilny identyfikator (np. slug profilu Useme albo
        fallback w postaci znormalizowanej nazwy).
        """
        results: list = []
        if not author_id or author_id.strip().lower() == "anonim":
            return results
        target = author_id.strip().lower()
        for path in self.magazyn_dir.rglob("*.json"):
            if path.name in {"marker.json"} or path.name.startswith("_"):
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if str(data.get("author_id", "")).strip().lower() == target:
                data["_path"] = str(path)
                results.append(data)
        return results

    def wszystkie_zlecenia(self) -> list:
        """Zwraca listę wszystkich rekordów zleceń z magazynu."""
        wyniki = []
        for path in self.magazyn_dir.rglob("*.json"):
            if ".checkpoints" in str(path) or path.name in {"marker.json"}:
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if "id" in data and "status" in data:
                    wyniki.append(data)
            except Exception:
                continue
        return wyniki

    def _update_marker(self, job_id: str, url: str) -> None:
        """Uaktualnia marker ostatnio wykrytej oferty (zapis atomowy)."""
        data = {
            "last_job_id": job_id,
            "last_job_url": url,
            "updated_at": datetime.now().isoformat()
        }
        atomic_write_json(MARKER_FILE, data)

    # --- CHECKPOINTY ŁAŃCUCHA AI ---
    def save_checkpoint(self, job_id: str, slot_id: str, context: Dict[str, Any]) -> Path:
        """Zapisuje atomowy checkpoint po ukończeniu slotu."""
        return save_checkpoint(job_id, slot_id, context, magazyn_dir=self.magazyn_dir)

    def load_checkpoint(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Wczytuje checkpoint zlecenia jeśli istnieje."""
        return load_checkpoint(job_id, magazyn_dir=self.magazyn_dir)

    def clear_checkpoint(self, job_id: str) -> bool:
        """Usuwa checkpoint po pełnym zakończeniu przetwarzania oferty."""
        return clear_checkpoint(job_id, magazyn_dir=self.magazyn_dir)


def save_checkpoint(job_id: str, slot_id: str, context: Dict[str, Any], magazyn_dir: Optional[Path] = None) -> Path:
    """Zapisuje atomowo stan pośredni przetwarzania zlecenia na dysk."""
    cdir = (magazyn_dir or MAGAZYN_DIR) / ".checkpoints"
    cdir.mkdir(parents=True, exist_ok=True)
    cp_file = cdir / f"{str(job_id).strip()}.json"
    
    # Oczyszczamy dane zlecenia z obiektów niebędących czystym JSON jeśli takie są
    cleaned_context = {}
    for k, v in context.items():
        if k == "_feedback":
            cleaned_context[k] = v
        elif k.startswith("_"):
            continue  # ignorujemy wewnętrzne cache typu _zlecenie
        else:
            cleaned_context[k] = v

    data = {
        "job_id": str(job_id).strip(),
        "last_completed_slot": str(slot_id).strip(),
        "saved_at": datetime.now().isoformat(),
        "context": cleaned_context
    }
    atomic_write_json(cp_file, data)
    return cp_file


def load_checkpoint(job_id: str, magazyn_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Wczytuje stan checkpointu z dysku."""
    cdir = (magazyn_dir or MAGAZYN_DIR) / ".checkpoints"
    cp_file = cdir / f"{str(job_id).strip()}.json"
    if not cp_file.exists():
        return None
    try:
        with open(cp_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and "last_completed_slot" in data and "context" in data:
                return data
            return None
    except Exception as e:
        print(f"[WARN] Błąd odczytu checkpointu {cp_file}: {e}")
        return None


def clear_checkpoint(job_id: str, magazyn_dir: Optional[Path] = None) -> bool:
    """Usuwa checkpoint zlecenia."""
    cdir = (magazyn_dir or MAGAZYN_DIR) / ".checkpoints"
    cp_file = cdir / f"{str(job_id).strip()}.json"
    if cp_file.exists():
        try:
            cp_file.unlink()
            return True
        except Exception as e:
            print(f"[WARN] Nie udało się usunąć checkpointu {cp_file}: {e}")
            return False
    return False
