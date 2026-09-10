"""Smoke test - czy Firefox 150 otworzy profil Firefox 152 (Camoufox)."""
import sys
import shutil
from pathlib import Path

SRC = Path(r"F:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135")  # kanoniczny (odblokowany sliderem)
DST = Path(r"F:\TEMP\playwright_ff_test_profile")

# Kopiuj profil do izolowanego katalogu zeby nie nadpisac Camoufox
if DST.exists():
    shutil.rmtree(DST, ignore_errors=True)
DST.parent.mkdir(parents=True, exist_ok=True)
print(f"Kopiowanie profilu {SRC} -> {DST} ...")
shutil.copytree(SRC, DST, dirs_exist_ok=True)
# usun parent.lock zeby Firefox nie odmowil otwarcia
(DST / "parent.lock").unlink(missing_ok=True)

from playwright.sync_api import sync_playwright

try:
    with sync_playwright() as p:
        ctx = p.firefox.launch_persistent_context(
            user_data_dir=str(DST),
            headless=True,
            timeout=30000,
        )
        page = ctx.new_page()
        page.goto("https://www.vinted.pl", timeout=30000)
        print("Title:", page.title())
        # sprawdz czy zalogowany
        r = page.evaluate("""async () => {
            try {
                const r = await fetch('/api/v2/users/current', {credentials: 'include'});
                const t = await r.text();
                let b = null; try { b = JSON.parse(t); } catch(e) {}
                return {status: r.status, body: t.slice(0,300), parsed: b};
            } catch(e) { return {error: String(e)}; }
        }""")
        print("users/current:", r)
        ctx.close()
except Exception as e:
    print(f"FAILED: {e!r}")
    sys.exit(1)
