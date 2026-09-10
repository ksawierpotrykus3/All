# coding: utf-8
import sys, time, json, traceback
from pathlib import Path

OUT = Path(r"F:\PROJEKTY\vinted\vinted\testy_camoufox\_login_out.txt")

def log(msg):
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg, flush=True)

PROFILE = sys.argv[1] if len(sys.argv) > 1 else r"F:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"  # kanoniczny (odblokowany sliderem)
log("=== profile: " + PROFILE)
log("t0 import")
from camoufox import Camoufox
log("t1 import ok")

try:
    log("t2 open context")
    with Camoufox(persistent_context=True, headless=True, user_data_dir=PROFILE, os="windows") as ctx:
        log("t3 context open")
        page = ctx.new_page()
        log("t4 new page")
        page.goto("https://www.vinted.pl/", wait_until="domcontentloaded", timeout=45000)
        log("t5 goto done: " + page.url)
        time.sleep(3)
        res = page.evaluate("""async () => {
            const r = await fetch('https://www.vinted.pl/api/v2/users/current', {credentials:'include', headers:{'Accept':'application/json'}});
            let body = null;
            try { body = await r.json(); } catch(e) { body = (await r.text()).slice(0,200); }
            return {status: r.status, body: body};
        }""")
        log("t6 result: " + json.dumps(res, ensure_ascii=False)[:1500])
except Exception as e:
    log("tFAIL: " + repr(e))
    log(traceback.format_exc())
log("DONE")