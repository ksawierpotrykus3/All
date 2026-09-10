# coding: utf-8
"""Sprawdza logowanie na profilu profil_firefox_135 i zapisuje wynik do pliku."""
from camoufox import Camoufox
import time, json, sys

PROFILE = r"F:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"
OUT = r"F:\PROJEKTY\vinted\vinted\testy_camoufox\docs\logs\_check_login_135_out.json"

result = {"status": None, "body": None, "error": None}

try:
    with Camoufox(persistent_context=True, headless=True,
                  user_data_dir=PROFILE, os="windows") as ctx:
        page = ctx.new_page()
        page.goto("https://www.vinted.pl/", wait_until="domcontentloaded", timeout=60000)
        time.sleep(4)
        res = page.evaluate("""async () => {
            const r = await fetch('https://www.vinted.pl/api/v2/users/current',
                {credentials: 'include', headers: {'Accept': 'application/json'}});
            let body = null;
            try { body = await r.json(); } catch (e) { body = (await r.text()).slice(0, 300); }
            return {status: r.status, body: body};
        }""")
        result["status"] = res.get("status")
        result["body"] = res.get("body")
except Exception as e:
    result["error"] = repr(e)

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(json.dumps(result, ensure_ascii=False)[:2000])