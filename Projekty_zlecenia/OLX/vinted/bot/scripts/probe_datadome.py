"""Probe: co DataDome serwuje teraz na profilu (slider? inny challenge? nic?)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PROFIL = r"f:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"
DEBUG = ROOT / "output" / "probe_datadome"


def main() -> int:
    DEBUG.mkdir(exist_ok=True)
    from camoufox import Camoufox
    from vintedbot.refresh import WEBGL_CONFIG

    with Camoufox(persistent_context=True, headless=True, user_data_dir=PROFIL,
                  os="windows", fingerprint_preset=True, humanize=True,
                  webgl_config=WEBGL_CONFIG) as ctx:
        page = ctx.new_page()
        page.goto("https://www.vinted.pl/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(6000)  # daj czas na ewentualny challenge
        page.screenshot(path=str(DEBUG / "glowna.png"), full_page=False)

        # Frame'y + URL-e (bez treści).
        frames = []
        for fr in getattr(page, "frames", []):
            frames.append(getattr(fr, "url", "") or "")
        print(f"[probe] frames ({len(frames)}):", flush=True)
        for u in frames:
            print(f"  - {u}", flush=True)

        # Informacja o ciasteczkach DataDome (sama obecność/rozmiar, NIE wartości).
        dd = [c for c in ctx.cookies() if "datadome" in (c.get("name", "").lower())
              or "captcha" in (c.get("name", "").lower())]
        print(f"[probe] cookies datadome/captcha: {len(dd)}", flush=True)
        for c in dd:
            v = str(c.get("value", ""))
            print(f"  - name={c.get('name')} host={c.get('domain')} len={len(v)} "
                  f"pref={v[:6]}...", flush=True)

        # Widoczna treść: czy jest tekst DataDome/captcha?
        txt = page.locator("body").inner_text(timeout=5000) if page.locator("body").count() else ""
        keys = [k for k in ("blocked", "captcha", "checking your browser", "verify",
                            "robot", "access denied", "poczekaj") if k.lower() in txt.lower()]
        print(f"[probe] tekst strony: {len(txt)} znaków; klucze: {keys}", flush=True)
        if txt:
            print("[probe] fragment:", txt[:300].replace("\n", " "), flush=True)

    # Rozmiary screenshotów.
    for p in sorted(DEBUG.glob("*.png")):
        print(f"[probe] {p.name}: {p.stat().st_size} B", flush=True)

    # Zapis wyników do JSON (stdout bywa tracony przez terminal).
    import json as _json
    out = {
        "frames": frames,
        "dd_cookies": [{"name": c.get("name"), "domain": c.get("domain"),
                        "len": len(str(c.get("value", "")))} for c in dd],
        "body_len": len(txt), "keywords": keys,
        "body_frag": txt[:300],
        "screenshots": [p.name for p in sorted(DEBUG.glob("*.png"))],
    }
    (ROOT / "output" / "probe_datadome.json").write_text(
        _json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
