# coding: utf-8
"""Weryfikacja: Camoufox 135 vs wbudowany curl_cffi firefox135 (tls.peet.ws).

Cel: potwierdzic, ze realny fingerprint Camoufox 135 (po pin + fetch) zgadza sie
z wbudowanym profilem curl_cffi firefox135:
  - curl_cffi firefox135: ja3_hash 6f7889b9fb1a62a9577e685c1fcfa919
                          ja4 t13d1717h2_5b57614c22b0_3cbfd9057e0d
                          peet_hash 89d89662b21018947a9a46658c4f5ede
                          cert_comp = [zlib, brotli, zstd]
"""
import json
from camoufox import Camoufox
from pathlib import Path

BASE = Path(__file__).resolve().parent
PROFILE = BASE / "profil_firefox_135"

CURL135 = {
    "ja3_hash": "6f7889b9fb1a62a9577e685c1fcfa919",
    "ja4": "t13d1717h2_5b57614c22b0_3cbfd9057e0d",
    "peet_hash": "89d89662b21018947a9a46658c4f5ede",
}

for lock in ("parent.lock", "lock", "lockfile"):
    p = PROFILE / lock
    try:
        if p.exists():
            p.unlink()
    except Exception:
        pass

with Camoufox(
    persistent_context=True,
    headless=False,
    user_data_dir=str(PROFILE),
    os="windows",
    fingerprint_preset=True,
    humanize=False,
    i_know_what_im_doing=True,
) as ctx:
    page = ctx.new_page()
    page.goto("https://tls.peet.ws/api/all", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)
    data = page.evaluate("() => { return JSON.parse(document.body.innerText); }")
    tls = data.get("tls", {})
    cert = None
    for e in tls.get("extensions", []):
        if e.get("name", "").startswith("compress_certificate"):
            cert = e.get("algorithms")
    got = {
        "ja3_hash": tls.get("ja3_hash"),
        "ja4": tls.get("ja4"),
        "peet_hash": tls.get("peetprint_hash"),
        "cert_comp": cert,
    }
    print(json.dumps(got, ensure_ascii=False, indent=2))
    for k, v in CURL135.items():
        print(f"{k}: match={got.get(k) == v} (curl={v[:40]} vs cxf={str(got.get(k))[:40]})")
    print("cert 3 algi:", got.get("cert_comp") == ["zlib (1)", "brotli (2)", "zstd (3)"])