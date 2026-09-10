# -*- coding: utf-8 -*-
"""Moduł AI Pipeline – w pełni odizolowany od mechaniki przeglądarki i magazynu.

Każdy model AI lub programista może łatwo modyfikować ten plik:
- zmieniać prompty,
- dodawać/usuwać kroki analizy i walidacji,
- zmieniać kryteria selekcji.
Przeglądarka i magazyn wywołują wyłącznie metody: `filter_offers` oraz `generate_proposal`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import USE_MOCK_AI

# Ścieżka do promptów (można swobodnie przestawiać pliki)
PROMPTS_DIR = Path(__file__).parent / "prompts"


@dataclass
class ProposalResult:
    """Zunifikowany wynik pracy modułu AI dla jednej oferty."""
    opis: str
    wycena: int
    dni: int
    powod_wyboru: str = ""
    metadata: Optional[Dict[str, Any]] = None


class BaseAIPipeline:
    """Interfejs bazowy dla łańcucha AI."""
    def filter_offers(self, offers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def generate_proposal(self, job_detail: Dict[str, Any]) -> ProposalResult:
        raise NotImplementedError


class MockAIPipeline(BaseAIPipeline):
    """Deterministyczny moduł testowy – do sprawdzania czy szkielet programu działa

    bez czekania na sieć, tokeny czy lokalne proxy DeepSeek.
    """
    def filter_offers(self, offers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Wybiera 1 zlecenie do precyzyjnego testu
        return offers[:1] if offers else []

    def generate_proposal(self, job_detail: Dict[str, Any]) -> ProposalResult:
        title = job_detail.get("title", "Zlecenie testowe")
        budget_str = str(job_detail.get("budget", "1500"))
        # Wyciągamy liczbę lub domyślne 1500 zł
        kwota = 1500
        for part in budget_str.replace(" ", "").split(","):
            digits = "".join(filter(str.isdigit, part))
            if digits:
                parsed = int(digits)
                if parsed >= 100:
                    kwota = parsed
                    break

        return ProposalResult(
            opis=f"Dzień dobry,\n\nZgłaszam swoją gotowość do realizacji zlecenia '{title}'.\nPosiadam doświadczenie w wymaganym zakresie i gwarantuję terminowe dowiezienie projektu.\n\nPozdrawiam,\nZespół",
            wycena=kwota,
            dni=7, # Zgodnie z regułą Useme: minimum 7 dni
            powod_wyboru="Deterministyczny mock dla testu szkieletu"
        )


class SlotChainAIPipeline(BaseAIPipeline):
    """Prawdziwy łańcuch AI wykorzystujący system slotów z chain_executor.py."""
    def __init__(self):
        try:
            from chain_executor import run_chain, call_deepseek, parse_ai_json_response
            self._run_chain = run_chain
            self._call_deepseek = call_deepseek
            self._parse_json = parse_ai_json_response
        except ImportError:
            self._run_chain = None
            self._call_deepseek = None
            self._parse_json = None

    def filter_offers(self, offers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Selekcja zleceń przez AI #1 na szybkim modelu (deepseek-v4-pro-nothink).

        Przyjmuje wszystkie nowe zlecenia (z pełnymi opisami), przepuszcza je
        przez kryteria selekcji oraz stack i filozofię. Zwraca wyłącznie
        te oferty, które otrzymały werdykt BIERZEMY.
        """
        if not offers:
            return []

        if not self._call_deepseek or not self._parse_json:
            print("[WARN] Brak chain_executor.py - zwracam wszystkie zlecenia")
            return [o for o in offers if o.get("id")]

        prompt_file = PROMPTS_DIR / "generatory" / "prompt_ai1.md"
        selekcja_file = PROMPTS_DIR / "kontekst" / "selekcja_zlecen.md"
        stack_file = PROMPTS_DIR / "kontekst" / "stack_i_filozofia.md"

        system_parts = []
        if prompt_file.exists():
            system_parts.append(prompt_file.read_text(encoding="utf-8-sig"))

        user_parts = []
        if selekcja_file.exists():
            user_parts.append("--- KRYTERIA SELEKCJI ---\n" + selekcja_file.read_text(encoding="utf-8-sig"))
        if stack_file.exists():
            user_parts.append("--- STACK I FILOZOFIA ---\n" + stack_file.read_text(encoding="utf-8-sig"))

        # Zestawienie zleceń do oceny (z pełnym opisem)
        zlecenia_do_analizy = []
        for o in offers:
            desc = o.get("full_description") or o.get("short_desc") or ""
            zlecenia_do_analizy.append({
                "id": str(o.get("id", "")),
                "title": o.get("title", ""),
                "budget": o.get("budget", ""),
                "category": o.get("category", ""),
                "description": desc[:4000]
            })

        user_parts.append("--- NOWE ZLECENIA DO OCENY ---\n" + json.dumps(zlecenia_do_analizy, ensure_ascii=False, indent=2))

        system_prompt = "\n\n".join(system_parts)
        user_prompt = "\n\n".join(user_parts)

        # Szybki model bez myślenia CoT (nothink) dla błyskawicznej selekcji
        odpowiedz = self._call_deepseek(
            system_prompt,
            user_prompt,
            model="deepseek-v4-pro-nothink",
            timeout=90,
            max_tokens=2000
        )

        if not odpowiedz:
            print("[WARN] Selekcjoner AI timeout lub brak odpowiedzi – fallback: przepuszczam wszystkie")
            return [o for o in offers if o.get("id")]

        parsed = self._parse_json(odpowiedz)

        if isinstance(parsed, dict) and not isinstance(parsed, list):
            for k in ("zlecenia", "oferty", "results", "items"):
                if isinstance(parsed.get(k), list):
                    parsed = parsed[k]
                    break

        wybrane_id = set()
        powody: Dict[str, str] = {}
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict):
                    jid = str(item.get("id", "")).strip()
                    werdykt = str(item.get("werdykt", "")).upper().strip()
                    powod = str(item.get("powod", "")).strip()
                    if werdykt in ("BIERZEMY", "TAK", "YES", "EDGE CASE", "EDGE_CASE") or "BIERZEMY" in werdykt or "EDGE" in werdykt:
                        wybrane_id.add(jid)
                        powody[jid] = powod
        else:
            for match in re.finditer(r'"id"\s*:\s*"(\d+)".*?"werdykt"\s*:\s*"(BIERZEMY|EDGE CASE|EDGE_CASE)"', odpowiedz, re.DOTALL | re.IGNORECASE):
                wybrane_id.add(match.group(1))

        zakwalifikowane = []
        for o in offers:
            oid = str(o.get("id", "")).strip()
            if oid in wybrane_id:
                o["selection_reason"] = powody.get(oid, "Wybrane przez Selekcjonera AI")
                zakwalifikowane.append(o)

        print(f"[SELEKCJA AI] Z {len(offers)} ofert zakwalifikowano {len(zakwalifikowane)}: {[o.get('id') for o in zakwalifikowane]}")
        return zakwalifikowane

    def generate_proposal(self, job_detail: Dict[str, Any]) -> ProposalResult:
        if not self._run_chain:
            raise RuntimeError("Nie znaleziono chain_executor.py!")

        job_id = str(job_detail.get("id", "brak_id"))
        wynik = self._run_chain(
            f"useme-job-{job_id}",
            job_detail,
            parent_id="useme-bot",
            parent_step=f"Generowanie wyceny i oferty #{job_id}",
        )
        if not wynik:
            raise RuntimeError(f"Łańcuch AI zwrócił błąd/abort dla zlecenia {job_id}")

        opis = str(wynik.get("opis", "")).strip()
        wycena_raw = wynik.get("wycena_dni", {})

        # Parsowanie wyceny i dni. Model zwraca tekst/markdown (nie dict), więc
        # szukamy twardego bloku [WYNIK_KONCOWY] KWOTA: X DNI: Y (zapas: dict).
        kwota, dni = _parse_wycena_dni(wycena_raw)

        return ProposalResult(
            opis=opis,
            wycena=kwota,
            dni=dni,
            powod_wyboru="Zaakceptowano przez walidatory slotowe",
            metadata=wynik
        )


def _parse_wycena_dni(wycena_raw: Any) -> tuple[int, int]:
    """Wyciąga kwotę i dni z outputu generatora wyceny.

    Kolejność bezpieczników:
    1. Jeśli model zwrócił dict (stary format) — czytamy klucze kwota/cena i dni.
    2. W przeciwnym razie szukamy twardego bloku: KWOTA: <n> oraz DNI: <n>.
    3. Brak rozpoznanej kwoty lub dni -> rzucamy błąd zamiast cichego fallbacku.
    """
    if isinstance(wycena_raw, dict):
        kwota = int(wycena_raw.get("kwota", wycena_raw.get("cena", 0)))
        dni = int(wycena_raw.get("dni", 0))
        return _waliduj(kwota, dni)

    tekst = str(wycena_raw or "")

    m_kwota = re.search(r"KWOTA\s*[:=]\s*([^\r\n]+)", tekst, re.IGNORECASE)
    m_dni = re.search(r"DNI\s*[:=]\s*(\d+)", tekst, re.IGNORECASE)

    kwota = _wyciagnij_kwote(m_kwota.group(1)) if m_kwota else 0
    dni = int(m_dni.group(1)) if m_dni else 0

    return _waliduj(kwota, dni)


def _wyciagnij_kwote(raw: str) -> int:
    """Pancernie czyści wartość kwoty: toleruje spacje, kropki, przecinki,
    grosze oraz dopiski zł/PLN. Np. '10 000 zł', '5.500 PLN', '6000,00 zł'."""
    # zostaw tylko cyfry, przecinki i kropki (wyrzuć 'zł', 'PLN', spacje)
    raw = re.sub(r"[^\d,.]", "", raw)
    # usuń grosze na końcu: '6000,00' -> '6000' (nie rusza '5.500' bo to 3 cyfry)
    raw = re.sub(r"[,.]\d{2}$", "", raw)
    cyfry = re.sub(r"[^\d]", "", raw)
    return int(cyfry) if cyfry else 0


def _waliduj(kwota: int, dni: int) -> tuple[int, int]:
    """Twarde minimum biznesowe: 500 zł i 7 dni. Brak wartości -> błąd."""
    if not kwota or not dni:
        raise ValueError(
            "Nie udało się wyciągnąć kwoty lub dni z outputu generatora wyceny. "
            "Sprawdź, czy prompt agent_02b zwraca blok [WYNIK_KONCOWY] z KWOTA i DNI."
        )
    kwota = max(500, kwota)
    dni = max(7, dni)
    return kwota, dni


def get_ai_pipeline() -> BaseAIPipeline:
    """Fabryka zwracająca aktywny pipeline AI na podstawie flagi w config.py."""
    if USE_MOCK_AI:
        return MockAIPipeline()
    return SlotChainAIPipeline()
