# coding: utf-8
"""Sprawdza czy profil_firefox_135 jest zalogowany (bez importu cookies z pliku)."""
from camoufox import Camoufox
import time

with Camoufox(persistent_context=True, headless=True,
              user_data_dir="profil_firefox_135", os="windows",
              fingerprint_preset=True, humanize=True,
              block_webgl=True, i_know_what_im_doing=True) as ctx:
    page = ctx.new_page()
    page.goto("https://www.vinted.pl/", wait_until="domcontentloaded", timeout=60000)
    time.sleep(3)
    check = page.evaluate("""async () => {
        const r = await fetch('/api/v2/users/current', {headers: {'Accept': 'application/json'}});
        const d = await r.json();
        return {status: r.status, login: (d.user||{}).login || d.login, id: (d.user||{}).id || d.id};
    }""")
    print("Zalogowany:", check)
