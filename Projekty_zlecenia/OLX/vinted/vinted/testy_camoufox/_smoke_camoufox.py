# coding: utf-8
import sys
from pathlib import Path

OUT = Path(r"F:\PROJEKTY\vinted\vinted\testy_camoufox\_smoke_out.txt")

def log(msg):
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg, flush=True)

log("start import")
try:
    from camoufox import Camoufox
    log("import ok")
except Exception as e:
    log("import FAIL: %r" % e)
    sys.exit(1)

log("open context")
try:
    with Camoufox(headless=True) as ctx:
        log("context opened")
        p = ctx.new_page()
        p.goto("about:blank")
        log("page title: %r" % p.title())
    log("context closed cleanly")
except Exception as e:
    log("runtime FAIL: %r" % e)
    sys.exit(2)

log("DONE")