# -*- coding: utf-8 -*-
"""KONTROLOWANY test realnej wysylki na JEDNYM projekcie (DRY_RUN=False)."""
import sys, json, time
from urllib.parse import urlencode
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import config
config.USE_MOCK_AI = False
from browser_driver import BrowserDriver
from form_driver import FormDriver, AccountBiddingBlockedError, convert_pln_to_currency
from ai_pipeline import get_ai_pipeline

with BrowserDriver(headless=False) as d:
    acc = d.check_account()
    print("[KONTO]", acc)

    # Wybierz 1 projekt IT, ktory AI zaakceptuje (Python/JS/AI automatyzacja)
    q = [("limit", 12), ("job_details", "true"), ("jobs[]", 13), ("jobs[]", 9), ("jobs[]", 1977),
         ("jobs[]", 913), ("webapp", 1), ("compact", True), ("new_errors", True), ("new_pools", True)]
    data = d._api_get_url("https://www.freelancer.pl/api/projects/0.1/projects/active/?" + urlencode(q))
    projs = sorted(data["result"]["projects"], key=lambda p: p.get("time_submitted") or 0, reverse=True)
    projs = [p for p in projs if not p.get("local") and not p.get("deleted")]
    pj = projs[0]
    print(f"[PROJEKT] #{pj['id']} {pj['title']} | cur={pj.get('currency',{}).get('code')}")

    det = d.fetch_job_details(pj["id"])
    det["currency"] = (pj.get("currency") or {}).get("code", "USD")
    det["seo_url"] = pj["seo_url"]

    ai = get_ai_pipeline()
    print("[AI] generuje oferte (moze potrwac)...")
    t0 = time.time()
    prop = ai.generate_proposal(det)
    print(f"[AI] gotowe w {time.time()-t0:.0f}s | PLN={prop.wycena} dni={prop.dni}")
    amt = convert_pln_to_currency(prop.wycena, det["currency"])
    print(f"[KONWERSJA] {prop.wycena} PLN -> {amt} {det['currency']}")

    form = FormDriver(d.context, dry_run=False)  # <-- REALNA WYSYLKA
    try:
        res = form.fill_and_prepare_offer(str(pj["id"]), pj["seo_url"], prop, currency=det["currency"])
        print("\n[WYNIK WYSYLKI]")
        print(json.dumps(res, ensure_ascii=False, indent=2))
    except AccountBiddingBlockedError as e:
        print("\n[ZABLOKOWANE]", e)
    except Exception as e:
        print("\n[BLAD]", type(e).__name__, e)