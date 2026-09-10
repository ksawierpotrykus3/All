# -*- coding: utf-8 -*-
"""Porownanie deterministyczne: DeepSeek (4571) vs Gemini (8045) na tym samym lancuchu.

Lancuch:
1. Slot 01: Research (model z dostepem do internetu)
2. Slot 02b: Wycena i dni (z wynikiem researchu)
3. Slot 02a: Tresc oferty (z wycena i researchem)
"""
import sys, json, re, time, requests
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = Path(r"c:\Users\Ksawier\Pictures\Screenshots\Projekty_autorskie\useme_core")
PROMPTS_DIR = BASE_DIR / "prompts"

DEEPSEEK_URL = "http://localhost:4571/v1/chat/completions"
GEMINI_URL = "http://localhost:8045/v1/chat/completions"

ENGINES = {
    "DeepSeek": {
        "url": DEEPSEEK_URL,
        "research_model": "deepseek-v4-pro-search",
        "gen_model": "deepseek-v4-pro-nothink",
    },
    "Gemini": {
        "url": GEMINI_URL,
        "research_model": "gemini-3.8-flash",
        "gen_model": "gemini-3.8-flash",
    }
}

def read_p(rel):
    return (PROMPTS_DIR / rel).read_text(encoding="utf-8-sig")

mechanika = read_p("kontekst/mechanika_wyceniania.md")
lore = read_p("kontekst/lore.md")
jak_pisac = read_p("kontekst/jak_pisac_oferty.md")

prompt_research = read_p("generatory/agent_01_research.md")
prompt_wycena = read_p("generatory/agent_02b_wycena_dni.md")
prompt_oferta = read_p("generatory/agent_02a_opis_oferty.md")

_CUT_MARKERS = ("Stream został przerwany", "Stream zostal przerwany")
_RESEARCH_QUERY_RE = re.compile(r"\[RESEARCH_QUERY\](.*?)(?:\[/RESEARCH_QUERY\]|$)", re.DOTALL | re.IGNORECASE)

def call_llm(url: str, model: str, system_prompt: str, user_prompt: str, timeout: int = 180, max_tokens: int = 3000) -> str:
    messages = []
    if system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    def _post(msgs):
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": msgs,
            "max_tokens": max_tokens,
            "stream": True,
        }
        for attempt in range(3):
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=(10, timeout), stream=True)
                if resp.status_code in (502, 503, 504):
                    time.sleep(2 * (attempt + 1))
                    continue
                resp.raise_for_status()
                full = ""
                for line in resp.iter_lines(decode_unicode=True):
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if delta:
                            full += delta
                    except Exception:
                        pass
                return full
            except Exception as e:
                time.sleep(2 * (attempt + 1))
        return ""

    out = _post(messages)
    for _ in range(3):
        if not any(m in out for m in _CUT_MARKERS):
            break
        for m in _CUT_MARKERS:
            idx = out.find(m)
            if idx != -1:
                out = out[:idx]
        messages.append({"role": "assistant", "content": out})
        messages.append({"role": "user", "content": "kontynuuj"})
        cont = _post(messages)
        if not cont.strip():
            break
        for m in _CUT_MARKERS:
            idx = cont.find(m)
            if idx != -1:
                cont = cont[:idx]
        out += cont

    return out

def run_pipeline(engine_name: str, job_tag: str, job_data_str: str):
    cfg = ENGINES[engine_name]
    url = cfg["url"]
    r_model = cfg["research_model"]
    g_model = cfg["gen_model"]

    print(f"\n==========================================", flush=True)
    print(f"[{engine_name.upper()}] Start: {job_tag}", flush=True)
    print(f"==========================================", flush=True)

    t0 = time.time()
    print(f"  [1/3] Krok 01: Research ({r_model})...", flush=True)
    research = call_llm(url, r_model, prompt_research, "--- DANE ZLECENIA ---\n" + job_data_str, timeout=180, max_tokens=4000)
    research = research or "BRAK_ISTOTNYCH_FAKTOW"
    t_res = time.time() - t0
    print(f"        Research gotowy ({len(research)} znakow, czas: {t_res:.1f}s)", flush=True)

    t1 = time.time()
    print(f"  [2/3] Krok 02b: Wycena ({g_model})...", flush=True)
    user_wycena = f"--- MECHANIKA ---\n{mechanika}\n\n--- DANE ZLECENIA ---\n{job_data_str}\n\n--- OUTPUT research ---\n{research}"
    wycena = call_llm(url, g_model, prompt_wycena, user_wycena, timeout=180, max_tokens=3000)

    m_q = _RESEARCH_QUERY_RE.search(wycena or "")
    if m_q:
        q_text = m_q.group(1).strip()
        print(f"        Model dopytuje: {q_text[:70]}...", flush=True)
        extra_r = call_llm(url, r_model, "Jestes agentem researchu. Odpowiedz zwiezle z faktami i URL.", q_text, timeout=120)
        wycena = call_llm(url, g_model, prompt_wycena, user_wycena + f"\n\n{wycena}\n\n--- WYNIK DODATKOWEGO RESEARCHU ---\n{extra_r}\n\nDokoncz: podaj finalna wycene z blokiem [WYNIK_KONCOWY].", timeout=180)

    t_wyc = time.time() - t1
    print(f"        Wycena gotowa ({len(wycena)} znakow, czas: {t_wyc:.1f}s)", flush=True)

    t2 = time.time()
    print(f"  [3/3] Krok 02a: Oferta ({g_model})...", flush=True)
    user_oferta = f"--- JAK PISAC ---\n{jak_pisac}\n\n--- LORE ---\n{lore}\n\n--- DANE ZLECENIA ---\n{job_data_str}\n\n--- OUTPUT research ---\n{research}\n\n--- OUTPUT wycena_dni ---\n{wycena}"
    oferta = call_llm(url, g_model, prompt_oferta, user_oferta, timeout=180, max_tokens=3000)

    m_qa = _RESEARCH_QUERY_RE.search(oferta or "")
    if m_qa:
        q_text_a = m_qa.group(1).strip()
        print(f"        Ofertownik dopytuje: {q_text_a[:70]}...", flush=True)
        extra_ra = call_llm(url, r_model, "Jestes agentem researchu. Odpowiedz zwiezle z faktami i URL.", q_text_a, timeout=120)
        oferta = call_llm(url, g_model, prompt_oferta, user_oferta + f"\n\n{oferta}\n\n--- WYNIK DODATKOWEGO RESEARCHU ---\n{extra_ra}\n\nDokoncz: napisz gotowa oferte.", timeout=180)

    t_ofe = time.time() - t2
    t_tot = time.time() - t0
    print(f"        Oferta gotowa ({len(oferta)} znakow, czas: {t_ofe:.1f}s) | Calosc: {t_tot:.1f}s", flush=True)

    m_kwota = re.search(r"KWOTA\s*[:=]\s*([0-9 ]+)", wycena or "")
    m_dni = re.search(r"DNI\s*[:=]\s*(\d+)", wycena or "")
    kwota = m_kwota.group(1).strip() if m_kwota else "?"
    dni = m_dni.group(1).strip() if m_dni else "?"

    return {
        "engine": engine_name,
        "job": job_tag,
        "kwota": kwota,
        "dni": dni,
        "total_time": t_tot,
        "research": research,
        "wycena": wycena,
        "oferta": oferta,
    }

JOBS = [
    ("Perca landing", BASE_DIR / "dane_badania" / "archiwum" / "it" / "143916_firma-perca-zleci-wykonanie-landing-page-na-swoja-strone" / "zlecenie.json"),
    ("Blog WordPress", BASE_DIR / "dane_badania" / "serwisy" / "143411_zlecenie-budowa-czystego-bloga-wordpress-generatepress-integ" / "zlecenie.json"),
]

def main():
    results = []
    for tag, path in JOBS:
        job = json.loads(path.read_text(encoding="utf-8-sig"))
        job_data_str = json.dumps(job, ensure_ascii=False, indent=2)

        for eng in ["DeepSeek", "Gemini"]:
            res = run_pipeline(eng, tag, job_data_str)
            results.append(res)

    out_file = BASE_DIR / "_compare_deepseek_vs_gemini_result.txt"
    lines = []
    lines.append("=" * 80)
    lines.append("RAPORT POROWNAWCZY: DEEPSEEK vs GEMINI (NA TYM SAMYM LANCUCHU)")
    lines.append("=" * 80 + "\n")

    for r in results:
        lines.append("############################################################")
        lines.append(f"ZLECENIE: {r['job']} | SILNIK: {r['engine']}")
        lines.append(f"KWOTA: {r['kwota']} zl | DNI: {r['dni']} | CZAS LACZNY: {r['total_time']:.1f}s")
        lines.append(f"############################################################\n")
        lines.append(f"--- 1. RESEARCH ({len(r['research'])} znakow) ---")
        lines.append(r['research'])
        lines.append(f"\n--- 2. WYCENA ({len(r['wycena'])} znakow) ---")
        lines.append(r['wycena'])
        lines.append(f"\n--- 3. OFERTA ({len(r['oferta'])} znakow) ---")
        lines.append(r['oferta'])
        lines.append("\n\n")

    out_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[ZAKONCZONO] Raport zapisany w: {out_file}", flush=True)

if __name__ == "__main__":
    main()
