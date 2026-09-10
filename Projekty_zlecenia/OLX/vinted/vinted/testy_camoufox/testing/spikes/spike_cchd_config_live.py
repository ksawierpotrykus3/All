# coding: utf-8
"""Pobierz publiczny JWT z metrics.vinted.lt/web/cchd_config przez curl_cffi.

Bezpieczenstwo: endpoint jest PUBLICZNY (cache-control: public, max-age=31536000),
nie wymaga cookies ani logowania. To NIE jest endpoint transakcyjny Vinted —
tylko publiczna konfiguracja SDK Incognia. Cel: rozbic JWT i sprawdzic, czy w
payloadzie jest klucz publiczny RSA (material do generowania x-incognia-request-token).
"""
import json
import base64
from curl_cffi import requests as creq

# Fingerprint Firefoksa 152 (zmierzony z Camoufox — wynik_ja3_firefox152.json).
FF152_JA3 = (
    "771,"
    "4865-4867-4866-49195-49199-52393-52392-49196-49200-49162-49171-49172-156-157-47-53,"
    "0-23-65281-10-11-35-16-5-34-18-51-43-13-45-28-27-65037,"
    "4588-29-23-24-25-256-257,"
    "0"
)
FF152_AKAMAI = "1:65536;2:0;4:131072;5:16384|12517377|0|m,p,a,s"
FF152_EXTRA_FP = {
    "tls_delegated_credential": (
        "ecdsa_secp256r1_sha256:ecdsa_secp384r1_sha384:"
        "ecdsa_secp521r1_sha512:ecdsa_sha1"
    ),
    "tls_record_size_limit": 16385,
    "tls_cert_compression": "zstd",
}

URLS = [
    "https://metrics.vinted.lt/web/cchd_config",
    "https://metrics.vinted.lt/web/pvt_cchd_config",
]


def _b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def main() -> None:
    out = {"results": []}
    for url in URLS:
        rec = {"url": url}
        try:
            r = creq.get(
                url,
                ja3=FF152_JA3,
                akamai=FF152_AKAMAI,
                extra_fp=FF152_EXTRA_FP,
                timeout=30,
            )
            rec["status"] = r.status_code
            rec["content_type"] = r.headers.get("content-type")
            body = r.text
            rec["body_len"] = len(body)

            if body.count(".") == 2:
                h, p, s = body.split(".")
                try:
                    rec["jwt_header"] = json.loads(_b64url_decode(h).decode("utf-8", "replace"))
                except Exception as exc:  # noqa: BLE001
                    rec["jwt_header_err"] = repr(exc)
                try:
                    rec["jwt_payload"] = json.loads(_b64url_decode(p).decode("utf-8", "replace"))
                except Exception as exc:  # noqa: BLE001
                    rec["jwt_payload_err"] = repr(exc)
                rec["jwt_sig_len"] = len(s)
                rec["jwt_raw"] = body
            else:
                rec["body"] = body[:2000]
        except Exception as exc:  # noqa: BLE001
            rec["error"] = repr(exc)

        print(json.dumps({k: v for k, v in rec.items() if k != "jwt_raw"}, ensure_ascii=False, indent=2))
        if "jwt_raw" in rec:
            print("JWT RAW:", rec["jwt_raw"][:600])
        out["results"].append(rec)

    with open("wynik_cchd_config_live.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print("\nZapisano: wynik_cchd_config_live.json")


if __name__ == "__main__":
    main()