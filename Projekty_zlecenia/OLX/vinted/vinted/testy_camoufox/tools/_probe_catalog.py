# coding: utf-8
"""Probe: właściwy profil + users/current + catalog."""
import json
from pathlib import Path

from camoufox import Camoufox

BASE_DIR = Path(__file__).resolve().parent
ROOT = BASE_DIR.parent
PROFILE_DIR = ROOT / "implementation" / "browser-profiles" / "profil_firefox_135"  # kanoniczny (odblokowany sliderem)

for lock in ("parent.lock", "lock", "lockfile"):
    p = PROFILE_DIR / lock
    try:
        if p.exists():
            p.unlink()
    except Exception:
        pass

with Camoufox(
    persistent_context=True,
    headless=True,
    user_data_dir=str(PROFILE_DIR),
    os="windows",
    fingerprint_preset=True,
    humanize=False,
    block_webgl=True,
    i_know_what_im_doing=True,
) as ctx:
    out = {}
    # users/current — sprawdzenie sesji
    r = ctx.request.get(
        "https://www.vinted.pl/api/v2/users/current",
        headers={"accept": "application/json", "locale": "pl-PL"},
    )
    out["users_current"] = {"status": r.status, "size": len(r.body())}
    try:
        out["users_current"]["uid"] = (r.json().get("user") or {}).get("id")
    except Exception:
        pass

    # katalog anonimowy
    r = ctx.request.get(
        "https://www.vinted.pl/api/v2/catalog/items?page=1&per_page=5&currency=PLN",
        headers={"accept": "application/json", "locale": "pl-PL"},
    )
    out["catalog"] = {"status": r.status, "size": len(r.body()),
                      "head": r.body()[:200].decode("utf-8", "ignore")}
    try:
        out["catalog"]["items"] = len(r.json().get("items", []))
    except Exception:
        pass

    # katalog z catalog_ids + filtrami jak w speed_trials
    r = ctx.request.get(
        "https://www.vinted.pl/api/v2/catalog/items"
        "?catalog_ids%5B%5D=44&price_to=50&order=newest_first&page=1&per_page=2&currency=PLN",
        headers={"accept": "application/json", "locale": "pl-PL"},
    )
    out["catalog_filt"] = {"status": r.status, "size": len(r.body())}
    try:
        out["catalog_filt"]["items"] = len(r.json().get("items", []))
    except Exception:
        pass

    print(json.dumps(out, ensure_ascii=False, indent=2), flush=True)
