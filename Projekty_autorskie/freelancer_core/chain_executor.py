# -*- coding: utf-8 -*-
"""Executor łańcucha AI (system slotów) – plug-and-play.

Odczytuje chain_config.json i odtwarza konfigurację slotów. Dla jednego
zlecenia odpala sloty sekwencyjnie: output generatora trafia do kontekstu
pod `output_key`, walidatory sprawdzają PASS/FAIL i mogą cofnąć łańcuch.

Postęp raportuje do Cortexa przez cortex_bridge.Chain.

Użycie:

    from chain_executor import run_chain

    wynik = run_chain("useme-oferty-1", zlecenie_dane)
    # wynik == {"opis": "...", "wycena_dni": "..."} lub None przy aborcie
"""

from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import requests

from cortex_bridge import Chain
from storage import clear_checkpoint, load_checkpoint, save_checkpoint

try:
    from wycena_kalkulator import policz_wycene, formatuj_wynik
except Exception:  # kalkulator opcjonalny – nie wywalaj lancucha
    policz_wycene = None
    formatuj_wynik = None

BASE_DIR = Path(__file__).parent
PROMPTS_DIR = BASE_DIR / "prompts"
CONFIG_PATH = PROMPTS_DIR / "chain_config.json"

# Czyste proxy passthrough (zero wstrzykiwania promptu kodowania)
DEEPSEEK_API_URL = "http://localhost:4571/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-v4-pro"
RESEARCH_MODEL = "deepseek-v4-flash-search"

# Twardy limit czasu jednego wywolania slotu. Bez tego proxy trzymajace
# otwarte polaczenie bez danych zawieszalo slot na domyslne 300s+.
SLOT_TIMEOUT = 120
# Globalny zegar śmierci na przetwarzanie pojedynczej oferty (6 minut max)
MAX_CHAIN_WALL_CLOCK_S = 360

_RESEARCH_QUERY_RE = re.compile(
    r"\[RESEARCH_QUERY\](.*?)(?:\[/RESEARCH_QUERY\]|$)", re.DOTALL | re.IGNORECASE
)


def _extract_research_query(text: str) -> Optional[str]:
    """Wyciąga pytanie badawcze z bloku [RESEARCH_QUERY]...[/RESEARCH_QUERY].

    Toleruje też niedomknięty blok (model często ucina zamykający tag przy
    streamingu) — wtedy bierzemy treść do końca tekstu.
    """
    m = _RESEARCH_QUERY_RE.search(text or "")
    if not m:
        return None
    q = m.group(1).strip()
    return q or None


# Mapowanie linii POPRAW_* z walidatora na id slotu-generatora, który ma je poprawić.
_FEEDBACK_TARGETS = {
    "POPRAW_WYCENA": "02b",
    "POPRAW_OFERTA": "02a",
}
_FEEDBACK_RE = re.compile(r"^\s*(POPRAW_[A-Z_]+)\s*:\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE)


def _extract_feedback(text: str) -> Dict[str, str]:
    """Wyciąga z odpowiedzi walidatora linie POPRAW_<KEY>: <wskazówka>.

    Zwraca dict {POPRAW_KEY: "wskazowka1\\nwskazowka2\\n..."}. Zbiera WSZYSTKIE
    wystąpienia danego klucza (walidator często zwraca kilka poprawek tego samego
    typu) i łączy je w jedną instrukcję. Pusty, gdy brak poprawek.
    """
    out: Dict[str, list[str]] = {}
    for m in _FEEDBACK_RE.finditer(text or ""):
        key = m.group(1).upper()
        val = m.group(2).strip()
        if val:
            out.setdefault(key, []).append(val)
    return {k: "\n".join(v) for k, v in out.items()}


_WYCENA_JSON_RE = re.compile(
    r"\[WYCENA_JSON\](.*?)(?:\[/WYCENA_JSON\]|$)", re.DOTALL | re.IGNORECASE
)


def _extract_wycena_json(text: str) -> Optional[Dict[str, Any]]:
    """Wyciąga strukturę JSON z bloku [WYCENA_JSON]...."""
    m = _WYCENA_JSON_RE.search(text or "")
    if not m:
        return None
    raw = m.group(1).strip()
    # usuń ewentualne ogrodzenia markdown
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        mm = re.search(r"\{.*\}", raw, re.DOTALL)
        if mm:
            try:
                return json.loads(mm.group(0))
            except json.JSONDecodeError:
                return None
    return None


def _do_research(query: str) -> str:
    """Odpala jeden krok researchu sieciowego przez proxy i zwraca fakty lub fallback."""
    system_prompt = (
        "Jesteś agentem researchu z dostępem do internetu. Odpowiedz na pytanie "
        "zwięźle po polsku. Podawaj wyłącznie fakty poparte źródłami (URL/cytat). "
        "Czego nie potwierdzisz, oznacz jako niepotwierdzone. Nigdy nie zmyślaj."
    )
    out = call_deepseek(
        system_prompt,
        "Sprawdź w sieci i odpowiedz: " + query,
        model=RESEARCH_MODEL,
        timeout=120,
        max_tokens=2000,
    )
    if not out or len(out.strip()) < 20:
        return "BRAK_ISTOTNYCH_FAKTOW"
    return out


def parse_ai_json_response(content: str) -> Any:
    """Czyści odpowiedź AI i wyodrębnia JSON (zapas dla surowych odpowiedzi)."""
    content = re.sub(r'<!-- PROXY_SID:.*?-->', '', content, flags=re.DOTALL).strip()
    if content.startswith("```"):
        lines = content.split("\n")
        start = 1 if lines[0].startswith("```") else 0
        end = -1 if lines[-1].startswith("```") else len(lines)
        content = "\n".join(lines[start:end]).strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {"raw_response": content}


def call_deepseek(system_prompt: str, user_prompt: str, max_tokens: int = 3000,
                  temperature: float = 0.7, timeout: int = 300,
                  model: str = DEEPSEEK_MODEL,
                  on_chunk: Optional[Callable[[str], None]] = None,
                  max_continues: int = 3) -> Optional[str]:
    """Wywołuje DeepSeek (localhost:4571 - czysty passthrough) z twardym watchdoggem.

    Prompt rozdzielony na rolę system (instrukcja) i user (dane/kontekst).
    Odpowiedź odczytywana strumieniowo (SSE). Każdy fragment trafia do
    on_chunk (jeśli podany). Zwraca pełny tekst lub None przy timeout.

    Auto-continue: gdy stream urwie się w połowie (proxy wstawia w treść
    „Stream został przerwany..." lub odpowiedź kończy się bez [DONE]), wysyłamy
    „kontynuuj" z dotychczasowym tekstem jako kontekstem i doklejamy wynik.
    """
    _CUT_MARKERS = ("Stream został przerwany", "Stream zostal przerwany")

    def _one_round(messages: list) -> Optional[str]:
        def _post() -> Optional[str]:
            headers = {"Content-Type": "application/json"}
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
            }
            last_err: Optional[Exception] = None
            session = requests.Session()
            try:
                # Retry TYLKO na szybkie bledy proxy (502/503/504). Timeoutow NIE ponawiamy.
                for attempt in range(2):
                    try:
                        resp = session.post(DEEPSEEK_API_URL, json=payload, headers=headers,
                                             timeout=(10, timeout), stream=True)
                        if resp.status_code in (502, 503, 504):
                            last_err = RuntimeError(f"proxy {resp.status_code}")
                            if attempt < 1:
                                time.sleep(2)
                                continue
                            return None
                        if resp.status_code != 200:
                            last_err = RuntimeError(f"http {resp.status_code}")
                            return None
                        full = ""
                        for line in resp.iter_lines(decode_unicode=True):
                            if not line:
                                continue
                            line = line.strip()
                            if not line.startswith("data:"):
                                continue
                            data_str = line[5:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                if delta:
                                    full += delta
                                    if on_chunk:
                                        on_chunk(delta)
                            except json.JSONDecodeError:
                                pass
                        return full
                    except requests.exceptions.RequestException as e:
                        # Blad sieci/timeout – nie ponawiamy dlugo, oddajemy fallback.
                        last_err = e
                        return None
            finally:
                session.close()

            if last_err:
                return None
            return ""

        box: Dict[str, Optional[str]] = {}
        def _run() -> None:
            try:
                box["result"] = _post()
            except Exception as e:  # nic nie moze uciec z watku
                box["result"] = None
                box["error"] = str(e)
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout + 15)
        if t.is_alive():
            print(f"[WATCHDOG] call_deepseek: watek przekroczyl limit {timeout + 15}s – przerywam oczekiwanie", flush=True)
            return None
        return box.get("result")

    messages: list = []
    if system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    full = _one_round(messages)
    if full is None:
        return None

    # Auto-continue, jeśli stream urwany albo odpowiedź nie domknęła się.
    for _ in range(max_continues):
        cut = any(m in full for m in _CUT_MARKERS)
        if not cut:
            break
        # usuń marker przerwania z treści, zachowując resztę jako kontekst
        for m in _CUT_MARKERS:
            idx = full.find(m)
            if idx != -1:
                full = full[:idx]
        messages.append({"role": "assistant", "content": full})
        messages.append({"role": "user", "content": "kontynuuj"})
        cont = _one_round(messages)
        if not cont or not cont.strip():
            break
        # kontynuacja też może nieść marker – zostanie złapany w kolejnej iteracji
        for m in _CUT_MARKERS:
            idx = cont.find(m)
            if idx != -1:
                cont = cont[:idx]
        full += cont

    return full


def _read_text(path: Path) -> str:
    # utf-8-sig toleruje (i usuwa) ewentualny BOM na początku pliku.
    return path.read_text(encoding="utf-8-sig")


def _slim_zlecenie(zlecenie: Dict[str, Any]) -> Dict[str, Any]:
    """Usuwa z danych zlecenia ciezkie smieci, ktorych pipeline nie potrzebuje.

    Lista konkurentow (po 60+ tagow + avatary) potrafi miec 30k znakow i rozdyma
    prompt do 85k+, przez co kazdy call AI jest wolny. Agentom wystarcza sama
    LICZBA ofert (competitors_count), nie lista kto zlozyl oferte.
    """
    if not isinstance(zlecenie, dict):
        return zlecenie
    slim = {k: v for k, v in zlecenie.items() if k not in ("competitors", "job_tags")}
    # zachowaj liczbe ofert, jesli nie ma jej wprost
    if "competitors_count" not in slim and "competitors" in zlecenie:
        try:
            slim["competitors_count"] = len(zlecenie["competitors"] or [])
        except Exception:
            pass
    return slim


def _load_config() -> Dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))


def _build_prompt(slot: Dict[str, Any], context: Dict[str, Any]) -> tuple[str, str]:
    """Składa prompt dla slotu na role: system (instrukcja) i user (dane + outputy)."""
    system_parts: list[str] = []
    user_parts: list[str] = []

    # Własny prompt slotu -> rola system
    if slot.get("prompt_file"):
        prompt_path = PROMPTS_DIR / slot["prompt_file"]
        if prompt_path.exists():
            system_parts.append(_read_text(prompt_path))

    # Pliki kontekstowe -> rola user
    for cf in slot.get("context_files", []):
        ctx_path = PROMPTS_DIR / cf
        if ctx_path.exists():
            user_parts.append(f"--- {cf} ---\n" + _read_text(ctx_path))

    # Dane zlecenia (zawsze dostępne) -> rola user
    zlecenie = context.get("_zlecenie")
    if zlecenie is not None:
        user_parts.append("--- DANE ZLECENIA ---\n" + json.dumps(zlecenie, ensure_ascii=False, indent=2))

    # Outputy poprzednich slotów -> rola user
    for key in slot.get("requires", []):
        if key in context:
            user_parts.append(f"--- OUTPUT {key} ---\n{context[key]}")

    # Feedback z walidatora (jeśli ten slot jest właśnie poprawiany) -> rola user
    feedback = context.get("_feedback", {})
    slot_feedback = feedback.get(slot.get("id"))
    if slot_feedback:
        user_parts.append(
            "--- OBOWIĄZKOWE POPRAWKI Z WERYFIKACJI ---\n"
            "Poprzednia wersja została odrzucona. Popraw DOKŁADNIE poniższe rzeczy, "
            "nie zmieniając niczego innego, co było poprawne:\n" + slot_feedback
        )

    return "\n\n".join(system_parts), "\n\n".join(user_parts)


def _is_pass(response: str) -> bool:
    """Walidator zwrócił PASS?"""
    head = response.strip().upper()
    return head.startswith("PASS") and not head.startswith("FAIL")


def run_chain(chain_id: str, zlecenie_dane: Dict[str, Any],
              parent_id: str = "useme-bot",
              parent_step: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Odpala łańcuch slotów dla jednego zlecenia z obsługą checkpointów i watchdogów.

    Raportuje postęp jako pod-łańcuch rodzica (parent_id/parent_step).
    Wznawia stan z dysku (.checkpoints/) jeśli poprzedni bieg został przerwany.
    Zwraca context z kluczami outputów lub None przy aborcie.
    """
    config = _load_config()
    retry_max = config.get("retry_max", 3)
    slots = [s for s in config["slots"] if s.get("enabled")]

    # Normalizacja danych wejściowych zlecenia (zarówno z bazy/archiwum jak i live scrapingu)
    _fields = (zlecenie_dane or {}).get("fields")
    if not _fields or not isinstance(_fields, dict):
        desc = (zlecenie_dane or {}).get("full_description") or (zlecenie_dane or {}).get("description") or (zlecenie_dane or {}).get("short_desc") or ""
        if desc:
            _fields = {
                "title": (zlecenie_dane or {}).get("title", ""),
                "description": desc,
                "budget": (zlecenie_dane or {}).get("budget", ""),
                "author": (zlecenie_dane or {}).get("author", "")
            }
            zlecenie_dane["fields"] = _fields
        else:
            _fields = {}

    # Guard: zlecenie bez danych wejsciowych (brak fields i brak opisu) nie ma z czym pracowac.
    if not _fields or len(json.dumps(_fields, ensure_ascii=False)) < 50:
        print(f"[SKIP] Zlecenie {zlecenie_dane.get('id','?')} bez danych wejściowych "
              f"(puste fields i brak opisu) - pomijam.", flush=True)
        return None

    # Odetnij ciezkie smieci (lista konkurentow), zanim trafia do promptow AI.
    zlecenie_dane = _slim_zlecenie(zlecenie_dane)
    job_id = str(zlecenie_dane.get("id", "tmp")).strip()

    context: Dict[str, Any] = {"_zlecenie": zlecenie_dane}

    # --- ODCZYT CHECKPOINTU ---
    cp = load_checkpoint(job_id)
    last_cp_slot = None
    if cp and isinstance(cp.get("context"), dict):
        last_cp_slot = cp.get("last_completed_slot")
        print(f"[CHECKPOINT] Znaleziono checkpoint dla #{job_id} (ostatni ukończony slot: {last_cp_slot})", flush=True)
        context.update(cp["context"])

    chain = Chain(
        chain_id,
        "Generator oferty Freelancer",
        opis="Generuje wycenę i treść oferty dla projektu z freelancer.pl",
        silnik="Python + DeepSeek (łańcuch AI)",
        wyzwalacz="manual",
        parent_id=parent_id,
        parent_step=parent_step,
    )

    i = 0
    # Jeśli mamy checkpoint, przeskocz ukończone sloty i oznacz je w Cortexie
    if last_cp_slot:
        last_idx = next((j for j, s in enumerate(slots) if s.get("id") == last_cp_slot), None)
        if last_idx is not None:
            print(f"[CHECKPOINT] Wznawiam od slotu {last_idx + 1}/{len(slots)} (pomijam {last_idx + 1} slotów)", flush=True)
            for prev_s in slots[:last_idx + 1]:
                with chain.step(prev_s["name"], typ="ai", opis="(Wczytano z checkpointu dyskowego)") as k_cp:
                    k_cp.status = "zrobione"
                    k_cp.wyjscie = str(context.get(prev_s.get("output_key", ""), "OK (z checkpointu)"))[:300]
                    k_cp.log("Pominięto generowanie – stan przywrócony z dysku.")
            i = last_idx + 1

    empty_retries = 0
    feedback_rounds = 0
    max_feedback_rounds = 1
    total_steps = 0
    max_total_steps = len(slots) + 5
    chain_start_time = time.time()

    while i < len(slots):
        total_steps += 1

        # 1. Twardy bezpiecznik liczby kroków (Koniec z pętlami nieskończonymi)
        if total_steps > max_total_steps:
            print(f"[CIRCUIT BREAKER] Zlecenie #{job_id}: Przekroczono limit kroków ({total_steps}/{max_total_steps}) – abort!", flush=True)
            with chain.step("Limit kroków przekroczony", typ="warunek") as k_err:
                k_err.status = "blad"
                k_err.wyjscie = "ABORT_STEP_LIMIT_EXCEEDED"
                k_err.log("Łańcuch zatrzymany przez Circuit Breaker – zbyt wiele ponowień/poprawek.")
            chain._zapisz()
            return None

        # 2. Twardy zegar śmierci (Wall-Clock Watchdog)
        elapsed = time.time() - chain_start_time
        if elapsed > MAX_CHAIN_WALL_CLOCK_S:
            print(f"[DEADLINE WATCHDOG] Zlecenie #{job_id}: Czas minął ({elapsed:.1f}s > {MAX_CHAIN_WALL_CLOCK_S}s) – abort!", flush=True)
            with chain.step("Zegar śmierci", typ="warunek") as k_err:
                k_err.status = "blad"
                k_err.wyjscie = "ABORT_WALL_CLOCK_TIMEOUT"
                k_err.log(f"Zlecenie przekroczyło dopuszczalny czas {MAX_CHAIN_WALL_CLOCK_S}s.")
            chain._zapisz()
            return None

        slot = slots[i]

        with chain.step(slot["name"],
                        typ="ai",
                        opis=slot.get("opis", "")) as krok:
            krok.narzedzie = "DeepSeek"
            krok.wejscie = json.dumps(zlecenie_dane, ensure_ascii=False, indent=2)
            system_prompt, user_prompt = _build_prompt(slot, context)
            krok.promptSystem = system_prompt
            krok.promptUser = user_prompt
            slot_model = slot.get("model", DEEPSEEK_MODEL)
            # Research sieciowy potrzebuje wiecej czasu niz zwykla generacja.
            slot_timeout = 240 if slot.get("id") == "01" else SLOT_TIMEOUT
            odpowiedz = call_deepseek(system_prompt, user_prompt, model=slot_model,
                                      timeout=slot_timeout, on_chunk=krok.stream)

            if slot["role"] == "generator":
                # Research slot (01): jeśli zwrócił pustkę, podstaw fallback
                is_fallback = False
                if slot.get("id") == "01":
                    if not odpowiedz or len(odpowiedz.strip()) < 20:
                        odpowiedz = "BRAK_ISTOTNYCH_FAKTOW"
                        is_fallback = True
                        krok.log("Research zwrócił pustkę – podstawiam deterministyczny BRAK_ISTOTNYCH_FAKTOW")

                # Generator 02b/02a: jeśli poprosił o dopytywanie researchu,
                # odpal wyszukiwanie i poproś model o dokończenie w tej samej turze.
                if slot.get("id") in ("02b", "02a"):
                    query = _extract_research_query(odpowiedz or "")
                    if query:
                        krok.log(f"Model prosi o research: {query[:80]}...")
                        research_wynik = _do_research(query)
                        kontynuacja = (
                            "\n\n--- WYNIK DODATKOWEGO RESEARCHU ---\n" + research_wynik +
                            "\n\nNa podstawie powyższego i wcześniejszych danych dokończ swoje zadanie. "
                            "Nie zwracaj już bloku [RESEARCH_QUERY]. Podaj finalny wynik."
                        )
                        odpowiedz = call_deepseek(
                            system_prompt,
                            user_prompt + "\n\n" + (odpowiedz or "") + kontynuacja,
                            model=slot_model,
                            on_chunk=krok.stream,
                        )

                # Slot 02b: model zwraca STRUKTURE (JSON), a kalkulator w Pythonie
                # liczy kwote deterministycznie. Podstawiamy wynik jako output.
                if slot.get("id") == "02b" and policz_wycene is not None:
                    struktura = _extract_wycena_json(odpowiedz or "")
                    if struktura:
                        try:
                            wynik = policz_wycene(struktura)
                            blok = formatuj_wynik(wynik)
                            ostrz = struktura.get("uzasadnienie", "")
                            odpowiedz = (
                                blok + "\n\n--- UZASADNIENIE DOBORU (model) ---\n" + str(ostrz) +
                                "\n\n--- ROZBICIE (kalkulator deterministyczny) ---\n" +
                                json.dumps(wynik["rozbicie"], ensure_ascii=False, indent=2)
                            )
                            if wynik.get("ostrzezenia"):
                                krok.log("Kalkulator: " + "; ".join(wynik["ostrzezenia"]))
                            krok.log(f"Kalkulator: {wynik['kwota']} zl / {wynik['dni']} dni (typ={wynik['typ']})")
                        except Exception as e:
                            krok.log(f"Kalkulator błąd: {e} – zostawiam odpowiedź modelu")
                    else:
                        krok.log("Brak bloku [WYCENA_JSON] – zostawiam odpowiedź modelu")

                # Sprawdzenie pustego wyniku (Z POPRAWIONYM WARUNKIEM FALLBACKU!)
                is_empty = not is_fallback and (odpowiedz is None or len(odpowiedz.strip()) < 30)
                if is_empty:
                    empty_retries += 1
                    err_desc = "timeout AI" if odpowiedz is None else f"pusty lub za krótki wynik ({len(odpowiedz.strip()) if odpowiedz else 0} znaków)"
                    if empty_retries > retry_max:
                        krok.log(f"BŁĄD KRYTYCZNY: {err_desc} po {empty_retries} próbach dla slotu {slot['id']} – abort łańcucha")
                        krok.wyjscie = "ABORT_EMPTY_OUTPUT"
                        return None
                    krok.log(f"Generator zwrócił {err_desc} – ponawiam próbę ({empty_retries}/{retry_max})...")
                    continue

                output_key = slot.get("output_key")
                if output_key:
                    context[output_key] = odpowiedz
                krok.wyjscie = odpowiedz
                krok.reasoning = odpowiedz

                # ZAPIS CHECKPOINTU PO POMYŚLNYM GENERATORZE
                save_checkpoint(job_id, slot["id"], context)
                krok.log(f"[CHECKPOINT] Zapisano stan po slocie {slot['id']}")

                i += 1
                empty_retries = 0

            elif slot["role"] == "validator":
                ok = _is_pass(odpowiedz) if (odpowiedz and odpowiedz.strip()) else False
                krok.wyjscie = "PASS" if ok else "FAIL"
                krok.reasoning = (odpowiedz or "")[:300]
                if ok:
                    save_checkpoint(job_id, slot["id"], context)
                    krok.log(f"[CHECKPOINT] Zapisano stan po walidatorze {slot['id']} (PASS)")
                    i += 1
                    empty_retries = 0
                else:
                    on_fail = slot.get("on_fail", "abort")
                    feedback = _extract_feedback(odpowiedz or "")
                    if feedback and feedback_rounds < max_feedback_rounds:
                        feedback_rounds += 1
                        context["_feedback"] = {
                            _FEEDBACK_TARGETS[k]: v
                            for k, v in feedback.items()
                            if k in _FEEDBACK_TARGETS
                        }
                        target = None
                        for key in ("POPRAW_WYCENA", "POPRAW_OFERTA"):
                            if key in feedback and key in _FEEDBACK_TARGETS:
                                target = _FEEDBACK_TARGETS[key]
                                break
                        if target is None:
                            krok.log("FAIL – nieznany cel poprawek – akceptuję wynik")
                            save_checkpoint(job_id, slot["id"], context)
                            i += 1
                            continue
                        idx = next((j for j, s in enumerate(slots) if s.get("id") == target), None)
                        if idx is None:
                            krok.log(f"nie znaleziono slotu {target} – akceptuję wynik")
                            save_checkpoint(job_id, slot["id"], context)
                            i += 1
                            continue
                        krok.log(f"FAIL – poprawki {list(feedback.keys())} -> retry od {target} "
                                 f"(runda {feedback_rounds}/{max_feedback_rounds})")
                        i = idx
                        continue

                    # Jeśli feedback wyczerpany lub brak wskazówek
                    if feedback:
                        krok.log(f"FAIL – limit rund feedbacku ({max_feedback_rounds}) – akceptuję najlepszy wynik")
                        save_checkpoint(job_id, slot["id"], context)
                        i += 1
                        continue

                    # Fallback dla starszych walidatorów
                    target = on_fail.replace("retry_from_", "")
                    idx = next((j for j, s in enumerate(slots) if s.get("id") == target), None)
                    if idx is None or on_fail == "abort":
                        krok.log("FAIL – abort walidatora")
                        return None

                    krok.log(f"FAIL – retry od {target}")
                    i = idx

    # Pełny sukces łańcucha – czyścimy checkpoint, bo oferta została sfinalizowana
    clear_checkpoint(job_id)
    print(f"[CHECKPOINT] Usunięto checkpoint #{job_id} po pełnym sukcesie łańcucha.", flush=True)

    chain._zapisz()
    # Usuń klucz wewnętrzny przed zwróceniem
    context.pop("_zlecenie", None)
    return context


if __name__ == "__main__":
    import sys

    # Zmuszamy konsolę Windows do UTF-8, żeby print nie wywalał się na
    # znakach unicode (np. „→”) przy kodowaniu cp1250.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    # Użycie:
    #   python chain_executor.py <pipeline_id> [dane_zlecenia.json]
    # pipeline_id trafia do Cortexa jako id pipeline'u (data/pipelines/<id>/stan.json).
    pipeline_id = sys.argv[1] if len(sys.argv) > 1 else "useme-oferty"

    if len(sys.argv) > 2:
        zlecenie = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8-sig"))
    else:
        # Smoke test – przykładowe zlecenie
        zlecenie = {
            "title": "Strona internetowa dla firmy",
            "budget": "do uzgodnienia",
            "description": "Potrzebuję nowoczesnej strony wizytówki.",
        }

    wynik = run_chain(pipeline_id, zlecenie)
    print(json.dumps({"opis_dlugosc": len(wynik.get("opis", "")) if wynik else None,
                      "wycena": wynik.get("wycena_dni", None)[:200] if wynik else None},
                     ensure_ascii=False, indent=2))