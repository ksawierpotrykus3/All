"""Test: czy build przechodzi z sekwencja Incognia (config->connectioncheck->cchd->consume) + AES-GCM token."""
import json
import subprocess
from pathlib import Path

from curl_cffi import requests as cr

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from vintedbot.config import wczytaj_cookies, tls_kwargs  # noqa: E402

COOKIES = Path(__file__).resolve().parents[1] / "output" / "cookies_152_export.txt"
OUT = Path(__file__).resolve().parents[1] / "output" / "incognia_sequence_test.json"


def b64url_json(seg: str):
    import base64
    pad = "=" * (-len(seg) % 4)
    return json.loads(base64.urlsafe_b64decode(seg + pad))


def main():
    cookies = wczytaj_cookies(str(COOKIES))
    base_h = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://www.vinted.pl",
        "Referer": "https://www.vinted.pl/",
    }
    out = {"kroki": []}

    def krok(nazwa, r, body=None):
        out["kroki"].append({
            "krok": nazwa, "status": r.status_code,
            "body_preview": (r.text or "")[:200],
            "payload": body,
        })
        return r

    # 1. config -> sdk_instance_id
    r = cr.get("https://api.vinted.pl/j3r4zw/v1/config", cookies=cookies, timeout=30, **tls_kwargs())
    krok("config", r)
    cfg = r.json() if r.status_code == 200 else {}
    sdk_id = cfg.get("sdk_instance_id") or cfg.get("sdkInstanceId")
    out["sdk_instance_id"] = sdk_id

    # 2. connectioncheck (POST) -> klucz publiczny?
    r = cr.post("https://conn-check.icg-in.com/connectioncheck", json={}, cookies=cookies, timeout=30, **tls_kwargs())
    krok("connectioncheck", r, body={})
    try:
        out["connectioncheck_json"] = r.json()
    except Exception:
        out["connectioncheck_json"] = None

    # 3. cchd_config (GET)
    r = cr.get("https://metrics.vinted.lt/web/cchd_config", cookies=cookies, timeout=30, **tls_kwargs())
    krok("cchd_config", r)
    try:
        hdr = (r.text or "").split(".")[0]
        out["cchd_config_jwe_header"] = b64url_json(hdr)
    except Exception:
        out["cchd_config_jwe_header"] = None

    # 4. consume (POST) type=pls - snapshot sygnalow (minimalny)
    consume_payload = {
        "v": 1, "type": "pls", "siid": sdk_id, "ts": 0, "t": 0,
        "s": {"webgl_renderer": "ANGLE (AMD, Radeon R9 200 Series Direct3D11 vs_5_0 ps_5_0)",
              "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0"},
    }
    r = cr.post("https://api.vinted.pl/j3r4zw/v1/consume", json=consume_payload, cookies=cookies, timeout=30, **tls_kwargs())
    krok("consume", r, body=consume_payload)

    # 5. token AES-GCM (istniejacy skrypt bota)
    tok = subprocess.run(
        ["node", "bot/scripts/generate_incognia_token.js", sdk_id or ""],
        capture_output=True, text=True, timeout=30,
    )
    token = tok.stdout.strip()
    out["token"] = token[:60] + "..."
    out["token_len"] = len(token)
    out["token_segments"] = len(token.split("."))

    # 6. build (realny, read-only test: item_id z parametru)
    import os
    item_id = int(os.environ.get("TEST_ITEM_ID", "9838061665"))
    r = cr.post(
        "https://www.vinted.pl/api/v2/purchases/checkout/build",
        json={"purchase_items": [{"id": item_id, "type": "item"}]},
        headers={**base_h, "x-incognia-request-token": token},
        cookies=cookies, timeout=30, **tls_kwargs(),
    )
    krok("build", r, body={"purchase_items": [{"id": item_id, "type": "item"}]})
    out["build_status"] = r.status_code
    try:
        out["build_json_keys"] = list((r.json() or {}).keys())
    except Exception:
        out["build_json_keys"] = None

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("sdk_instance_id", "token_segments", "build_status")}, ensure_ascii=False))
    for k in out["kroki"]:
        print(f"  {k['krok']}: {k['status']}")


if __name__ == "__main__":
    main()
