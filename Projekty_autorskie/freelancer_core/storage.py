# -*- coding: utf-8 -*-
"""Magazyn ofert (Storage & Deduplication).

Zarządza bazą pobranych zleceń w useme_core/magazyn/:
- deduplikacja: sprawdza czy zlecenie o danym ID/URL już istnieje,
- zapisywanie surowych danych i pełnych detali,
- aktualizacja statusu: NOWA -> WYBRANA_AI -> PRZYGOTOWANA -> WYSLANA (lub DRY_RUN_OK).
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
        temp_file.replace(p)
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
        name = str(category_url_or_name).lower()
        for slug in ("programowanie-i-it", "web-dev", "automation-ai",
                     "sklepy-shopify", "scraping-dane"):
            if slug in name:
                return slug
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
