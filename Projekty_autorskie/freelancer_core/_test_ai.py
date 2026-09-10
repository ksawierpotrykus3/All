# -*- coding: utf-8 -*-
"""Test realnego lancucha AI na jednym projekcie (bez wysylki)."""
import sys, json, time
from urllib.parse import urlencode
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import config
config.USE_MOCK_AI = False
from browser_driver import BrowserDriver
from ai_pipeline import get_ai_pipeline

with BrowserDriver(headless=True) as d:
    q = [("limit", 8), ("job_details", "true"), ("jobs[]", 13), ("jobs[]", 3), ("jobs[]", 9),
         ("webapp", 1), ("compact", True), ("new_errors", True), ("new_pools", True)]
    data = d._api_get_url("https://www.freelancer.pl/api/projects/0.1/projects/active/?" + urlencode(q))
    projs = sorted(data["result"]["projects"], key=lambda p: p.get("time_submitted") or 0, reverse=True)
    projs = [p for p in projs if not p.get("local") and not p.get("deleted")]
    pj = projs[0]
    print("[PROJEKT]", pj["id"], pj["title"])
    det = d.fetch_job_details(pj["id"])
    print("[OPIS dl.]", len(det.get("full_description", "")))

    ai = get_ai_pipeline()
    print("[AI] klasa:", type(ai).__name__)
    print("[AI] selekcja...")
    t0 = time.time()
    wybrane = ai.filter_offers([det])
    print(f"[AI] wybrano {len(wybrane)} (czas {time.time()-t0:.1f}s)")
    if wybrane:
        print("[AI] generowanie oferty...")
        t0 = time.time()
        prop = ai.generate_proposal(det)
        print(f"[AI] czas {time.time()-t0:.1f}s")
        print("=== OPIS OFERTY ===")
        print(prop.opis[:2000])
        print("=== WYCENA:", prop.wycena, "| DNI:", prop.dni)