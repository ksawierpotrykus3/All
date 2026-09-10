# coding: utf-8
"""Porównanie wbudowanych profili firefox curl_cffi vs prawdziwy FF152 (tls.peet.ws).
Klucz: cert_compression (ext 27) — FF152 ogłasza zlib+brotli+zstd (3 naraz).
Wbudowany profil, który też ma 3, jest KOMPLETNY i może pasować do datadome FF."""
import json
from curl_cffi import requests as cr

TARGET_CERT = ["zlib (1)", "brotli (2)", "zstd (3)"]

for imp in ["firefox133", "firefox135", "firefox144", "firefox147"]:
    try:
        r = cr.get("https://tls.peet.ws/api/all", impersonate=imp, timeout=30)
        d = r.json()
        tls = d.get("tls", {})
        ext = tls.get("extensions", [])
        cert = None
        for e in ext:
            if e.get("name", "").startswith("compress_certificate"):
                cert = e.get("algorithms")
        print(f"=== {imp} ===")
        print(f"  ja3_hash   : {tls.get('ja3_hash')}")
        print(f"  ja4        : {tls.get('ja4')}")
        print(f"  peet_hash  : {tls.get('peetprint_hash')}")
        print(f"  cert_comp  : {cert}")
        print(f"  match_3alg : {cert == TARGET_CERT}")
    except Exception as e:
        print(f"=== {imp} === ERROR: {e}")