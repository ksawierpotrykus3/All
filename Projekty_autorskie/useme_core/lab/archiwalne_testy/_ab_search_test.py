# -*- coding: utf-8 -*-
"""Test A/B: osobny research (obecnie) vs search wbudowany w chat (nowy DeepSeek).

Wariant A (obecny mechanizm):
  01 research (model -search) -> 02b (-nothink) -> 02a (-nothink)
  + dopytywanie [RESEARCH_QUERY] dla 02b/02a

Wariant B (search w srodku chatu):
  brak slotu 01; 02b i 02a na modelu -search (search wbudowany),
  bez mechanizmu dopytywania.
"""
import sys, json, re, time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = Path(r"c:\Users\Ksawier\Pictures\Screenshots\Projekty_autorskie\useme_core")
P = BASE / "prompts"
sys.path.insert(0, str(BASE))

from chain_executor import call_deepseek, _extract_research_query, _do_research


def rtxt(rel):
    return (P / rel).read_text(encoding="utf-8-sig")


def strip_research_section(text):
    return re.sub(r"\n## Dopytywanie researchu.*?(?=\n## |\Z)", "\n", text, flags=re.DOTALL)


# --- kontekst ---
mechanika = rtxt("kontekst/mechanika_wyceniania.md")
lore = rtxt("kontekst/lore.md")
jak_pisac = rtxt("kontekst/jak_pisac_oferty.md")

research_prompt = rtxt("generatory/agent_01_research.md")
wycena_prompt = rtxt("generatory/agent_02b_wycena_dni.md")
oferta_prompt = rtxt("generatory/agent_02a_opis_oferty.md")

wycena_prompt_bez = strip_research_section(wycena_prompt)
oferta_prompt_bez = strip_research_section(oferta_prompt)


def run_variant_a(job, dane, tag):
    print(f"\n===== WARIANT A ({tag}) =====", flush=True)
    research = call_deepseek(research_prompt, "--- DANE ZLECENIA ---\n" + dane,
                             model="deepseek-v4-pro-search", timeout=180, max_tokens=4000)
    research = research or "BRAK_ISTOTNYCH_FAKTOW"
    print(f"  research dlugosc: {len(research)}", flush=True)

    # 02b z dopytywaniem
    w1 = call_deepseek(wycena_prompt, "--- MECHANIKA ---\n" + mechanika + "\n\n--- DANE ZLECENIA ---\n" + dane + "\n\n--- OUTPUT research ---\n" + research,
                       model="deepseek-v4-pro-nothink", timeout=180, max_tokens=2500) or ""
    q = _extract_research_query(w1)
    if q:
        print(f"  02b dopytal: {q[:80]}", flush=True)
        rz = _do_research(q)
        wycena = call_deepseek(wycena_prompt, "--- MECHANIKA ---\n" + mechanika + "\n\n--- DANE ZLECENIA ---\n" + dane + "\n\n--- OUTPUT research ---\n" + research + "\n\n" + w1 + "\n\n--- WYNIK DODATKOWEGO RESEARCHU ---\n" + rz + "\n\nDokoncz: finalna wycena z [WYNIK_KONCOWY]. Bez [RESEARCH_QUERY].",
                            model="deepseek-v4-pro-nothink", timeout=180, max_tokens=2500) or ""
    else:
        print("  02b nie dopytal", flush=True)
        wycena = w1

    o1 = call_deepseek(oferta_prompt, "--- JAK PISAC ---\n" + jak_pisac + "\n\n--- LORE ---\n" + lore + "\n\n--- DANE ZLECENIA ---\n" + dane + "\n\n--- OUTPUT research ---\n" + research + "\n\n--- OUTPUT wycena_dni ---\n" + wycena,
                       model="deepseek-v4-pro-nothink", timeout=180, max_tokens=2500) or ""
    qa = _extract_research_query(o1)
    if qa:
        print(f"  02a dopytal: {qa[:80]}", flush=True)
        rza = _do_research(qa)
        oferta = call_deepseek(oferta_prompt, "--- JAK PISAC ---\n" + jak_pisac + "\n\n--- LORE ---\n" + lore + "\n\n--- DANE ZLECENIA ---\n" + dane + "\n\n--- OUTPUT research ---\n" + research + "\n\n--- OUTPUT wycena_dni ---\n" + wycena + "\n\n" + o1 + "\n\n--- WYNIK DODATKOWEGO RESEARCHU ---\n" + rza + "\n\nDokoncz: napisz finalna oferte. Bez [RESEARCH_QUERY].",
                            model="deepseek-v4-pro-nothink", timeout=180, max_tokens=2500) or ""
    else:
        print("  02a nie dopytal", flush=True)
        oferta = o1
    return research, wycena, oferta, q, qa


def run_variant_b(job, dane, tag):
    print(f"\n===== WARIANT B ({tag}) ===== (search wbudowany w chat)", flush=True)
    # 02b na modelu -search (bez osobnego researchu, bez dopytywania)
    wycena = call_deepseek(wycena_prompt_bez, "--- MECHANIKA ---\n" + mechanika + "\n\n--- DANE ZLECENIA ---\n" + dane,
                           model="deepseek-v4-pro-search", timeout=240, max_tokens=2500) or ""
    # 02a na modelu -search
    oferta = call_deepseek(oferta_prompt_bez, "--- JAK PISAC ---\n" + jak_pisac + "\n\n--- LORE ---\n" + lore + "\n\n--- DANE ZLECENIA ---\n" + dane + "\n\n--- OUTPUT wycena_dni ---\n" + wycena,
                           model="deepseek-v4-pro-search", timeout=240, max_tokens=2500) or ""
    return wycena, oferta


def extract_kwota(text):
    m = re.search(r"KWOTA:\s*([0-9 ]+)", text or "")
    d = re.search(r"DNI:\s*([0-9]+)", text or "")
    return (m.group(1).strip() if m else "?"), (d.group(1).strip() if d else "?")


JOBS = [
    ("Perca landing", BASE / "dane_badania" / "archiwum" / "it" / "143916_firma-perca-zleci-wykonanie-landing-page-na-swoja-strone" / "zlecenie.json"),
    ("Blog WordPress", BASE / "dane_badania" / "serwisy" / "143411_zlecenie-budowa-czystego-bloga-wordpress-generatepress-integ" / "zlecenie.json"),
]

out_lines = []
for tag, path in JOBS:
    job = json.loads(path.read_text(encoding="utf-8-sig"))
    dane = json.dumps(job, ensure_ascii=False, indent=2)

    ra, wa, oa, qb, qa = run_variant_a(job, dane, tag)
    ka, da = extract_kwota(wa)

    wb, ob = run_variant_b(job, dane, tag)
    kb, db = extract_kwota(wb)

    out_lines.append(
        f"########## ZLECENIE: {tag} ##########\n\n"
        f"===== A: RESEARCH 01 (dlugosc {len(ra)}) =====\n{ra}\n\n"
        f"===== A: DOPYTANIA =====\n02b: {qb}\n02a: {qa}\n\n"
        f"===== A: WYCENA (KWOTA={ka}, DNI={da}) =====\n{wa}\n\n"
        f"===== A: OFERTA =====\n{oa}\n\n\n"
        f"===== B: WYCENA search-w-chacie (KWOTA={kb}, DNI={db}) =====\n{wb}\n\n"
        f"===== B: OFERTA search-w-chacie =====\n{ob}\n\n\n"
    )
    print(f"\n>>> {tag}: A=({ka} zl/{da} dni)  B=({kb} zl/{db} dni)", flush=True)

out = BASE / "_ab_search_result.txt"
out.write_text("\n".join(out_lines), encoding="utf-8")
print("\nDONE ->", out, flush=True)