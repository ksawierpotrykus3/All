# coding: utf-8
"""Zbiera swieze cookies z auto-login profilu Camoufox do fresh_cookies.json."""
import json
import time
from pathlib import Path

from camoufox import Camoufox

BASE = Path(__file__).resolve().parent.parent.parent
PROFILE = str(BASE / "implementation" / "browser-profiles" / "profil_firefox_135")  # kanoniczny profil
OUT = BASE / "implementation" / "curl-cffi" / "fresh_cookies.json"


def main():
    with Camoufox(persistent_context=True, headless=True,
                  user_data_dir=PROFILE, os="windows",
                  fingerprint_preset=True, humanize=True) as ctx:
        page = ctx.new_page()
        page.goto("https://www.vinted.pl/", wait_until="domcontentloaded", timeout=60000)
        time.sleep(4)

        ok = False
        raw = ""
        for _ in range(30):
            try:
                d = page.evaluate(
                    "async () => { const r = await fetch('/api/v2/users/current',"
                    " {headers:{'Accept':'application/json'}});"
                    " const t = await r.text(); return {s:r.status, t:t}; }"
                )
                raw = d.get("t", "")
                if d.get("s") == 200:
                    ok = True
                    break
            except Exception:
                pass
            time.sleep(2)

        print(f"users/current status={'200' if ok else 'nie-200'}")
        print(f"body head: {raw[:300]}")

        cookies = ctx.cookies()
        OUT.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"cookies: {len(cookies)} -> {OUT}")


if __name__ == "__main__":
    main()