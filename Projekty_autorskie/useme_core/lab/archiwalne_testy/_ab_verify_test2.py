# -*- coding: utf-8 -*-
"""Test v2: petla weryfikacji az do PASS (max 3 rundy). Sprawdza czy autokorekta
realnie dochodzi do czystej oferty i wiarygodnej wyceny.

Dla kazdego zlecenia:
  research 01 (z retry przy pustce) -> 02b -> 02a -> [08 verify -> poprawki -> 02b/02a] x3
"""
import sys, json, re
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = Path(r"c:\Users\Ksawier\Pictures\Screenshots\Projekty_autorskie\useme_core")
P = BASE / "prompts"
sys.path.insert(0, str(BASE))

from chain_executor import call_deepseek, _extract_research_query, _do_research, _extract_feedback


def rtxt(rel):
    return (P / rel).read_text(encoding="utf-8-sig")


mechanika = rtxt("kontekst/mechanika_wyceniania.md")
lore = rtxt("kontekst/lore.md")
jak_pisac = rtxt("kontekst/jak_pisac_oferty.md")
research_prompt = rtxt("generatory/agent_01_research.md")
wycena_prompt = rtxt("generatory/agent_02b_wycena_dni.md")
oferta_prompt = rtxt("generatory/agent_02a_opis_oferty.md")
weryfik_prompt = rtxt("walidatory/agent_08_weryfikacja_zasadd.md")


def gen_research(dane):
    for attempt in range(3):
        r = call_deepseek(research_prompt, "--- DANE ZLECENIA ---\n" + dane,
                          model="deepseek-v4-pro-search", timeout=200, max_tokens=4000)
        if r and len(r.strip()) > 500:
            return r
        print(f"    research pusty/krotki (proba {attempt+1}), retry...", flush=True)
    return r or "BRAK_ISTOTNYCH_FAKTOW"


def gen_wycena(dane, research, feedback=""):
    user = "--- MECHANIKA ---\n" + mechanika + "\n\n--- LORE ---\n" + lore + \
           "\n\n--- DANE ZLECENIA ---\n" + dane + "\n\n--- OUTPUT research ---\n" + research
    if feedback:
        user += "\n\n--- OBOWIAZKOWE POPRAWKI Z WERYFIKACJI (zastosuj wszystkie) ---\n" + feedback
    w = call_deepseek(wycena_prompt, user, model="deepseek-v4-pro-nothink", timeout=200, max_tokens=3000) or ""
    q = _extract_research_query(w)
    if q:
        rz = _do_research(q)
        w = call_deepseek(wycena_prompt, user + "\n\n" + w + "\n\n--- WYNIK DODATKOWEGO RESEARCHU ---\n" + rz + "\n\nDokoncz: finalna wycena z [WYNIK_KONCOWY]. Bez [RESEARCH_QUERY].",
                          model="deepseek-v4-pro-nothink", timeout=200, max_tokens=3000) or ""
    return w


def gen_oferta(dane, research, wycena, feedback=""):
    user = "--- JAK PISAC ---\n" + jak_pisac + "\n\n--- LORE ---\n" + lore + \
           "\n\n--- DANE ZLECENIA ---\n" + dane + "\n\n--- OUTPUT research ---\n" + research + \
           "\n\n--- OUTPUT wycena_dni ---\n" + wycena
    if feedback:
        user += "\n\n--- OBOWIAZKOWE POPRAWKI Z WERYFIKACJI (zastosuj wszystkie) ---\n" + feedback
    o = call_deepseek(oferta_prompt, user, model="deepseek-v4-pro-nothink", timeout=200, max_tokens=3000) or ""
    q = _extract_research_query(o)
    if q:
        rz = _do_research(q)
        o = call_deepseek(oferta_prompt, user + "\n\n" + o + "\n\n--- WYNIK DODATKOWEGO RESEARCHU ---\n" + rz + "\n\nDokoncz: napisz finalna oferte. Bez [RESEARCH_QUERY].",
                          model="deepseek-v4-pro-nothink", timeout=200, max_tokens=3000) or ""
    return o


def verify(dane, research, wycena, oferta):
    user = ("--- JAK PISAC OFERTY (zasady) ---\n" + jak_pisac +
            "\n\n--- MECHANIKA WYCENIANIA (zasady) ---\n" + mechanika +
            "\n\n--- DANE ZLECENIA ---\n" + dane +
            "\n\n--- OUTPUT research ---\n" + research +
            "\n\n--- WYCENA (do sprawdzenia) ---\n" + wycena +
            "\n\n--- OFERTA (do sprawdzenia) ---\n" + oferta)
    return call_deepseek(weryfik_prompt, user, model="deepseek-v4-pro-nothink", timeout=200, max_tokens=2500) or ""


def kwota_dni(text):
    m = re.search(r"KWOTA:\s*([0-9 ]+)", text or "")
    d = re.search(r"DNI:\s*([0-9]+)", text or "")
    return (m.group(1).strip() if m else "?"), (d.group(1).strip() if d else "?")


JOBS = [
    ("Perca landing", BASE / "dane_badania" / "archiwum" / "it" / "143916_firma-perca-zleci-wykonanie-landing-page-na-swoja-strone" / "zlecenie.json"),
    ("Blog WordPress", BASE / "dane_badania" / "serwisy" / "143411_zlecenie-budowa-czystego-bloga-wordpress-generatepress-integ" / "zlecenie.json"),
]

out = []
for tag, path in JOBS:
    job = json.loads(path.read_text(encoding="utf-8-sig"))
    dane = json.dumps(job, ensure_ascii=False, indent=2)
    print(f"\n########## {tag} ##########", flush=True)

    research = gen_research(dane)
    print(f"  research: {len(research)} znakow", flush=True)

    wycena = gen_wycena(dane, research)
    oferta = gen_oferta(dane, research, wycena)
    k, d = kwota_dni(wycena)
    print(f"  RUNDA 0 (naiwna): {k} zl / {d} dni", flush=True)

    sections = [f"===== RESEARCH 01 (dl. {len(research)}) =====\n{research}\n",
                f"===== RUNDA 0: WYCENA ({k} zl / {d} dni) =====\n{wycena}\n",
                f"===== RUNDA 0: OFERTA =====\n{oferta}\n"]

    for runda in range(1, 4):
        verdict = verify(dane, research, wycena, oferta)
        v_clean = verdict.strip()
        print(f"  WERYFIKACJA runda {runda}: {v_clean[:120].replace(chr(10),' | ')}", flush=True)
        sections.append(f"===== WERYFIKACJA runda {runda} =====\n{verdict}\n")
        if v_clean.upper().startswith("PASS"):
            print(f"  -> PASS w rundzie {runda}", flush=True)
            break
        fb = _extract_feedback(verdict)
        sections.append(f"===== POPRAWKI runda {runda} (parsowane) =====\n{json.dumps(fb, ensure_ascii=False, indent=2)}\n")
        if not fb:
            print("  -> FAIL bez parsowalnych poprawek, stop", flush=True)
            break
        if "POPRAW_WYCENA" in fb:
            wycena = gen_wycena(dane, research, fb["POPRAW_WYCENA"])
        if "POPRAW_OFERTA" in fb:
            oferta = gen_oferta(dane, research, wycena, fb["POPRAW_OFERTA"])
        k, d = kwota_dni(wycena)
        print(f"  RUNDA {runda} (po poprawie): {k} zl / {d} dni", flush=True)
        sections.append(f"===== RUNDA {runda}: WYCENA ({k} zl / {d} dni) =====\n{wycena}\n")
        sections.append(f"===== RUNDA {runda}: OFERTA =====\n{oferta}\n")

    out.append(f"########## {tag} ##########\n\n" + "\n".join(sections) + "\n\n")

res = BASE / "_ab_verify_result2.txt"
res.write_text("\n".join(out), encoding="utf-8")
print("\nDONE ->", res, flush=True)