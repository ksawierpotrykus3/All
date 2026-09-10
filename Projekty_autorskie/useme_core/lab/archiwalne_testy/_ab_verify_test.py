# -*- coding: utf-8 -*-
"""Test: czy walidator 08 + autokorekta poprawia oferte i wycene.

Dla kazdego zlecenia:
  1. Wygeneruj wycene (02b) i oferte (02a) z researchem 01 [wersja NAIWNA]
  2. Uruchom weryfikator 08
  3. Jesli FAIL -> popraw wg wskazowek i zweryfikuj ponownie [wersja POPRAWIONA]
Zapisuje wszystko do _ab_verify_result.txt
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
    r = call_deepseek(research_prompt, "--- DANE ZLECENIA ---\n" + dane,
                      model="deepseek-v4-pro-search", timeout=180, max_tokens=4000)
    return r or "BRAK_ISTOTNYCH_FAKTOW"


def gen_wycena(dane, research, feedback=""):
    user = "--- MECHANIKA ---\n" + mechanika + "\n\n--- LORE ---\n" + lore + \
           "\n\n--- DANE ZLECENIA ---\n" + dane + "\n\n--- OUTPUT research ---\n" + research
    if feedback:
        user += "\n\n--- OBOWIAZKOWE POPRAWKI Z WERYFIKACJI ---\n" + feedback + \
                "\n\nPopraw DOKLADNIE te rzeczy, reszte zostaw."
    w = call_deepseek(wycena_prompt, user, model="deepseek-v4-pro-nothink", timeout=180, max_tokens=2500) or ""
    q = _extract_research_query(w)
    if q:
        rz = _do_research(q)
        w = call_deepseek(wycena_prompt, user + "\n\n" + w + "\n\n--- WYNIK DODATKOWEGO RESEARCHU ---\n" + rz + "\n\nDokoncz: finalna wycena z [WYNIK_KONCOWY]. Bez [RESEARCH_QUERY].",
                          model="deepseek-v4-pro-nothink", timeout=180, max_tokens=2500) or ""
    return w


def gen_oferta(dane, research, wycena, feedback=""):
    user = "--- JAK PISAC ---\n" + jak_pisac + "\n\n--- LORE ---\n" + lore + \
           "\n\n--- DANE ZLECENIA ---\n" + dane + "\n\n--- OUTPUT research ---\n" + research + \
           "\n\n--- OUTPUT wycena_dni ---\n" + wycena
    if feedback:
        user += "\n\n--- OBOWIAZKOWE POPRAWKI Z WERYFIKACJI ---\n" + feedback + \
                "\n\nPopraw DOKLADNIE te rzeczy, reszte zostaw."
    o = call_deepseek(oferta_prompt, user, model="deepseek-v4-pro-nothink", timeout=180, max_tokens=2500) or ""
    q = _extract_research_query(o)
    if q:
        rz = _do_research(q)
        o = call_deepseek(oferta_prompt, user + "\n\n" + o + "\n\n--- WYNIK DODATKOWEGO RESEARCHU ---\n" + rz + "\n\nDokoncz: napisz finalna oferte. Bez [RESEARCH_QUERY].",
                          model="deepseek-v4-pro-nothink", timeout=180, max_tokens=2500) or ""
    return o


def verify(dane, research, wycena, oferta):
    user = ("--- JAK PISAC OFERTY (zasady) ---\n" + jak_pisac +
            "\n\n--- MECHANIKA WYCENIANIA (zasady) ---\n" + mechanika +
            "\n\n--- DANE ZLECENIA ---\n" + dane +
            "\n\n--- OUTPUT research ---\n" + research +
            "\n\n--- WYCENA (do sprawdzenia) ---\n" + wycena +
            "\n\n--- OFERTA (do sprawdzenia) ---\n" + oferta)
    return call_deepseek(weryfik_prompt, user, model="deepseek-v4-pro-nothink", timeout=180, max_tokens=2000) or ""


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
    print(f"  research: {len(research)}", flush=True)

    wycena0 = gen_wycena(dane, research)
    oferta0 = gen_oferta(dane, research, wycena0)
    k0, d0 = kwota_dni(wycena0)
    print(f"  NAIWNA: {k0} zl / {d0} dni", flush=True)

    verdict0 = verify(dane, research, wycena0, oferta0)
    print(f"  WERYFIKACJA 1: {verdict0[:200].replace(chr(10),' | ')}", flush=True)

    fb = _extract_feedback(verdict0)
    wycena1, oferta1 = wycena0, oferta0
    verdict1 = "PASS (bez zmian – weryfikator nie zglosil poprawek)"
    if fb:
        if "POPRAW_WYCENA" in fb:
            wycena1 = gen_wycena(dane, research, fb["POPRAW_WYCENA"])
        if "POPRAW_OFERTA" in fb:
            oferta1 = gen_oferta(dane, research, wycena1, fb["POPRAW_OFERTA"])
        verdict1 = verify(dane, research, wycena1, oferta1)
        print(f"  WERYFIKACJA 2: {verdict1[:200].replace(chr(10),' | ')}", flush=True)
    k1, d1 = kwota_dni(wycena1)
    print(f"  POPRAWIONA: {k1} zl / {d1} dni", flush=True)

    out.append(
        f"########## {tag} ##########\n\n"
        f"===== RESEARCH 01 (dl. {len(research)}) =====\n{research}\n\n"
        f"===== WYCENA NAIWNA ({k0} zl / {d0} dni) =====\n{wycena0}\n\n"
        f"===== OFERTA NAIWNA =====\n{oferta0}\n\n"
        f"===== WERYFIKACJA #1 =====\n{verdict0}\n\n"
        f"===== POPRAWKI (parsowane) =====\n{json.dumps(fb, ensure_ascii=False, indent=2)}\n\n"
        f"===== WYCENA PO POPRAWIE ({k1} zl / {d1} dni) =====\n{wycena1}\n\n"
        f"===== OFERTA PO POPRAWIE =====\n{oferta1}\n\n"
        f"===== WERYFIKACJA #2 =====\n{verdict1}\n\n\n"
    )

res = BASE / "_ab_verify_result.txt"
res.write_text("\n".join(out), encoding="utf-8")
print("\nDONE ->", res, flush=True)