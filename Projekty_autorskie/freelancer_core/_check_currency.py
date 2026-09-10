# -*- coding: utf-8 -*-
"""Sprawdza walute formularza i budzet projektu."""
import sys, json
from urllib.parse import urlencode
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from browser_driver import BrowserDriver

with BrowserDriver(headless=False) as d:
    q = [("limit", 8), ("job_details", "true"), ("jobs[]", 13), ("webapp", 1),
         ("compact", True), ("new_errors", True), ("new_pools", True)]
    data = d._api_get_url("https://www.freelancer.pl/api/projects/0.1/projects/active/?" + urlencode(q))
    projs = sorted(data["result"]["projects"], key=lambda p: p.get("time_submitted") or 0, reverse=True)
    projs = [p for p in projs if not p.get("local") and not p.get("deleted")]
    for pj in projs[:5]:
        print(f"#{pj['id']} | {pj['title'][:40]:40} | budget={pj.get('budget')} | cur={pj.get('currency',{}).get('code')}")

    pj = projs[0]
    print(f"\n=== FORMULARZ dla #{pj['id']} ({pj.get('currency',{}).get('code')}) ===")
    page = d.context.new_page()
    page.goto(f"https://www.freelancer.pl/projects/{pj['seo_url']}/details", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector("button:has-text('Złóż ofertę')", timeout=20000)
    page.locator("button:has-text('Złóż ofertę')").first.click()
    page.wait_for_timeout(4000)
    # Tekst wokol pola kwoty
    area = page.evaluate("""() => {
        const el = document.querySelector('#bidAmountInput');
        if (!el) return 'brak';
        let p = el.closest('div'); let out = [];
        for (let i=0;i<4 && p;i++){ out.push(p.innerText); p = p.parentElement; }
        return out.join(' ||| ').slice(0,500);
    }""")
    print("[KONTEKST POLA KWOTY]:", area)
    page.close()