# coding: utf-8
"""Render screena bramki z redirect_url uzyskanego przez curl_cffi.

Sciezka zakupowa jest W 100% przez curl_cffi. Ten skrypt jedynie RENDERUJE
juz-wygenerowany redirect_url do wizualnego dowodu (screenshot z wypalonym
timestampem ms) - nie wykonuje zadnej transakcji. Nie otwieramy screena.

Uzycie: python render_bramka.py [wynik.json] [prefiks]
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR.parent / "implementation" / "browser-profiles" / "profil_firefox_135"  # kanoniczny (odblokowany sliderem)


def wall_ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3] + "Z"


def main():
    src_name = sys.argv[1] if len(sys.argv) > 1 else "wynik_bench_gateway_nocam.json"
    prefix = sys.argv[2] if len(sys.argv) > 2 else "bramka_nocam"
    src = BASE_DIR / src_name
    data = json.loads(src.read_text(encoding="utf-8"))
    redirect_url = data.get("redirect_url")
    to_gateway_ms = data.get("elapsed", {}).get("to_gateway_ms")
    ts_start = data.get("ts_start")
    if not redirect_url:
        print("BRAK redirect_url w wyniku", flush=True)
        return

    shot_path = BASE_DIR / f"{prefix}_{int(time.time() * 1000)}.png"

    from camoufox import Camoufox

    try:
        with Camoufox(
            persistent_context=True, headless=True,
            user_data_dir=str(PROFILE_DIR), os="windows",
            fingerprint_preset=True, humanize=True, block_webgl=True,
        ) as ctx:
            page = ctx.new_page()
            page.goto(redirect_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(4000)
            page.screenshot(path=str(shot_path), full_page=False)
        print(f"screenshot zapisany: {shot_path}", flush=True)
    except Exception as e:
        print(f"BLAD screena: {e}", flush=True)
        return

    # wypal timestamp ms
    try:
        img = Image.open(shot_path).convert("RGB")
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 30)
        except Exception:
            font = ImageFont.load_default()
        gw_txt = f"+{to_gateway_ms:.0f} ms" if to_gateway_ms is not None else "BRAK"
        line = (f"curl_cffi -> BRAMKA | T0={ts_start} | dotarcie={gw_txt} | "
                f"shot={wall_ts()} | payment=pending")
        bar_h = 48
        draw.rectangle([0, img.height - bar_h, img.width, img.height], fill=(0, 0, 0))
        draw.text((12, img.height - bar_h + 8), line, fill=(255, 255, 0), font=font)
        marked = BASE_DIR / f"{prefix}_dowod.png"
        img.save(marked)
        print(f"dowod: {marked}", flush=True)
    except Exception as e:
        print(f"BLAD znakowania: {e}", flush=True)


if __name__ == "__main__":
    main()