"""Probe 2: czy interstitial DataDome ("Verifying you are human") rozwiazuje sie sam
w headless po dłuższym czekaniu / reload, i kiedy pojawia się iframe captcha-delivery."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PROFIL = r"f:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"
DEBUG = ROOT / "output" / "probe_datadome2"


def main() -> int:
    DEBUG.mkdir(exist_ok=True)
    from camoufox import Camoufox
    from vintedbot.refresh import WEBGL_CONFIG

    def stan(page, ctx):
        dd = [c for c in ctx.cookies()
              if "datadome" in (c.get("name", "").lower())
              or "captcha" in (c.get("name", "").lower())]
        frames = [getattr(fr, "url", "") or "" for fr in getattr(page, "frames", [])]
        txt = ""
        if page.locator("body").count():
            try:
                txt = page.locator("body").inner_text(timeout=2000)
            except Exception:
                pass
        return {
            "t": round(time.monotonic(), 1),
            "dd": [{"name": c.get("name"), "len": len(str(c.get("value", ""))),
                    "pref": str(c.get("value", ""))[:6]} for c in dd],
            "frames": frames,
            "txt": txt[:120].replace("\n", " "),
        }

    with Camoufox(persistent_context=True, headless=True, user_data_dir=PROFIL,
                  os="windows", fingerprint_preset=True, humanize=True,
                  webgl_config=WEBGL_CONFIG) as ctx:
        page = ctx.new_page()
        page.goto("https://www.vinted.pl/", wait_until="domcontentloaded", timeout=60000)
        historia = [stan(page, ctx)]
        print(f"[p2] t=0: {historia[0]}", flush=True)
        for i in range(12):  # ~60s obserwacji
            time.sleep(5)
            historia.append(stan(page, ctx))
            print(f"[p2] t={historia[-1]['t']}: dd={historia[-1]['dd']} "
                  f"captcha_frame={any('captcha' in f for f in historia[-1]['frames'])} "
                  f"txt={historia[-1]['txt'][:60]}", flush=True)
            if "captcha" in " ".join(historia[-1]["frames"]):
                page.screenshot(path=str(DEBUG / "slider_wykryty.png"))
        page.screenshot(path=str(DEBUG / "koniec.png"), full_page=False)
        # Dodatkowo reload i sprawdzenie.
        page.reload(wait_until="domcontentloaded", timeout=60000)
        time.sleep(8)
        historia.append(stan(page, ctx))
        print(f"[p2] po reload: {historia[-1]}", flush=True)
        page.screenshot(path=str(DEBUG / "po_reload.png"), full_page=False)

    (ROOT / "output" / "probe_datadome2.json").write_text(
        json.dumps(historia, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
