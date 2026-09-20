# -*- coding: utf-8 -*-
import sys, json, re
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(r"c:\Users\Ksawier\Pictures\Screenshots\Projekty_autorskie\useme_core")
P = BASE / "prompts"
sys.path.insert(0, str(BASE))

from chain_executor import call_deepseek, _extract_research_query, _do_research

def rtxt(rel):
    return (P / rel).read_text(encoding="utf-8-sig")

job = json.loads((BASE / "dane_badania" / "archiwum" / "serwisy" / "143654_ustawienie-podatkow-shopify-usa-ue-vat-ioss" / "zlecenie.json").read_text(encoding="utf-8-sig"))
dane = json.dumps(job, ensure_ascii=False, indent=2)

# Pliki kontekstowe
mechanika = rtxt("kontekst/mechanika_wyceniania.md")
lore = rtxt("kontekst/lore.md")
jak_pisac = rtxt("kontekst/jak_pisac_oferty.md")

research_prompt = rtxt("generatory/agent_01_research.md")
wycena_prompt_raw = rtxt("generatory/agent_02b_wycena_dni.md")
oferta_prompt_raw = rtxt("generatory/agent_02a_opis_oferty.md")

# Wycinam sekcje dopytywania z promptow (do grupy kontrolnej)
def strip_research_section(text):
    return re.sub(r"\n## Dopytywanie researchu.*?(?=\n## |\Z)", "\n", text, flags=re.DOTALL)

wycena_prompt_bez = strip_research_section(wycena_prompt_raw)
oferta_prompt_bez = strip_research_section(oferta_prompt_raw)

# 1. RESEARCH 01 (raz, wspolny dla obu grup)
print("=== KROK 1: RESEARCH 01 ===", flush=True)
research = call_deepseek(research_prompt, "--- DANE ZLECENIA ---\n" + dane, model="deepseek-v4-pro-search", timeout=180, max_tokens=4000)
research = research or "BRAK_ISTOTNYCH_FAKTOW"
print("Research dlugosc:", len(research), flush=True)

# Grupa 1 (kontrola): brak mozliwosci dopytywania
print("\n=== KROK 2: GRUPA 1 (bez dodatkowego researchu) ===", flush=True)
wycena_1 = call_deepseek(
    wycena_prompt_bez,
    "--- MECHANIKA ---\n" + mechanika + "\n\n--- LORE ---\n" + lore + "\n\n--- DANE ZLECENIA ---\n" + dane + "\n\n--- OUTPUT research ---\n" + research,
    model="deepseek-v4-pro-nothink", timeout=180, max_tokens=3000
) or ""

oferta_1 = call_deepseek(
    oferta_prompt_bez,
    "--- JAK PISAC ---\n" + jak_pisac + "\n\n--- LORE ---\n" + lore + "\n\n--- DANE ZLECENIA ---\n" + dane + "\n\n--- OUTPUT research ---\n" + research + "\n\n--- OUTPUT wycena_dni ---\n" + wycena_1,
    model="deepseek-v4-pro-nothink", timeout=180, max_tokens=3000
) or ""

# Grupa 2 (eksperyment): wymuszony dodatkowy research dla 02b i 02a
force = "\n\n[WAZNE DO TESTU] MUSISZ zadac dokladnie jedno dodatkowe pytanie badawcze w bloku [RESEARCH_QUERY]...[/RESEARCH_QUERY] zanim dasz finalny wynik. To obowiazkowe."
print("\n=== KROK 3: GRUPA 2 (wymuszony dodatkowy research) ===", flush=True)

# --- 02b Grupa 2 ---
wycena_2_r1 = call_deepseek(
    wycena_prompt_raw + force,
    "--- MECHANIKA ---\n" + mechanika + "\n\n--- LORE ---\n" + lore + "\n\n--- DANE ZLECENIA ---\n" + dane + "\n\n--- OUTPUT research ---\n" + research,
    model="deepseek-v4-pro-nothink", timeout=180, max_tokens=1000
) or ""
q_b = _extract_research_query(wycena_2_r1)
print("  02b zapytal:", repr(q_b), flush=True)
if q_b:
    rz_b = _do_research(q_b)
    wycena_2 = call_deepseek(
        wycena_prompt_raw,
        "--- MECHANIKA ---\n" + mechanika + "\n\n--- LORE ---\n" + lore + "\n\n--- DANE ZLECENIA ---\n" + dane + "\n\n--- OUTPUT research ---\n" + research + "\n\n" + wycena_2_r1 + "\n\n--- WYNIK DODATKOWEGO RESEARCHU ---\n" + rz_b + "\n\nDokoncz: daj finalna wycene z blokiem [WYNIK_KONCOWY]. Bez [RESEARCH_QUERY].",
        model="deepseek-v4-pro-nothink", timeout=180, max_tokens=3000
    ) or ""
else:
    wycena_2 = wycena_2_r1

# --- 02a Grupa 2 ---
oferta_2_r1 = call_deepseek(
    oferta_prompt_raw + force,
    "--- JAK PISAC ---\n" + jak_pisac + "\n\n--- LORE ---\n" + lore + "\n\n--- DANE ZLECENIA ---\n" + dane + "\n\n--- OUTPUT research ---\n" + research + "\n\n--- OUTPUT wycena_dni ---\n" + wycena_2,
    model="deepseek-v4-pro-nothink", timeout=180, max_tokens=1000
) or ""
q_a = _extract_research_query(oferta_2_r1)
print("  02a zapytal:", repr(q_a), flush=True)
if q_a:
    rz_a = _do_research(q_a)
    oferta_2 = call_deepseek(
        oferta_prompt_raw,
        "--- JAK PISAC ---\n" + jak_pisac + "\n\n--- LORE ---\n" + lore + "\n\n--- DANE ZLECENIA ---\n" + dane + "\n\n--- OUTPUT research ---\n" + research + "\n\n--- OUTPUT wycena_dni ---\n" + wycena_2 + "\n\n" + oferta_2_r1 + "\n\n--- WYNIK DODATKOWEGO RESEARCHU ---\n" + rz_a + "\n\nDokoncz: napisz finalna oferte. Bez [RESEARCH_QUERY].",
        model="deepseek-v4-pro-nothink", timeout=180, max_tokens=3000
    ) or ""
else:
    oferta_2 = oferta_2_r1

# Zapis
out = BASE / "_ab_test_result.txt"
out.write_text(
    "========== RESEARCH 01 (wspolny) ==========\n" + research + "\n\n\n"
    "========== GRUPA 1 (BEZ dodatkowego researchu) ==========\n\n"
    "--- WYCENA ---\n" + wycena_1 + "\n\n--- OFERTA ---\n" + oferta_1 + "\n\n\n"
    "========== GRUPA 2 (Z wymuszonym dodatkowym researchem) ==========\n\n"
    "--- 02b zapytal ---\n" + repr(q_b) + "\n\n--- WYCENA ---\n" + wycena_2 + "\n\n"
    "--- 02a zapytal ---\n" + repr(q_a) + "\n\n--- OFERTA ---\n" + oferta_2 + "\n",
    encoding="utf-8"
)
print("\nDONE", out, flush=True)