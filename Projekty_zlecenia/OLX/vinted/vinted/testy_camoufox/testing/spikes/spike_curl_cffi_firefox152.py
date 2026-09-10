# coding: utf-8
"""Test: czy curl_cffi potrafi odtworzyc JA3/JA4 Firefoksa 152 (Camoufox).

Bezpieczenstwo: request wychodzi TYLKO do tls.peet.ws (publiczny serwis TLS
fingerprintingu), NIE do Vinted. Cel naukowy: zweryfikowac, czy curl_cffi z
wlasnym ja3+akamai+extra_fp generuje ten sam JA3 hash co realny Firefox 152
(zmierzone w spike_ja3_firefox152.py).
"""
import json
from curl_cffi import requests as creq

# Wartosci zmierzone z realnego Firefoksa 152 (Camoufox) — wynik_ja3_firefox152.json
FF152_JA3 = (
    "771,"
    "4865-4867-4866-49195-49199-52393-52392-49196-49200-49162-49171-49172-156-157-47-53,"
    "0-23-65281-10-11-35-16-5-34-18-51-43-13-45-28-27-65037,"
    "4588-29-23-24-25-256-257,"
    "0"
)
FF152_AKAMAI = "1:65536;2:0;4:131072;5:16384|12517377|0|m,p,a,s"

# Rozszerzenia specyficzne dla Firefoksa (spoza standardowego JA3):
# - delegated_credentials (34): algorytmy sygnatur (colon-separated)
# - record_size_limit (28): 16385 (0x4001)
FF152_EXTRA_FP = {
    "tls_delegated_credential": (
        "ecdsa_secp256r1_sha256:ecdsa_secp384r1_sha384:"
        "ecdsa_secp521r1_sha512:ecdsa_sha1"
    ),
    "tls_record_size_limit": 16385,
    "tls_cert_compression": "zstd",  # Firefox 152 oferuje zlib, brotli, zstd
}

# Realna lista signature_algorithms FF152 (z wynik_ja3_firefox152.json)
FF152_SIGALGS = [
    "ecdsa_secp256r1_sha256",
    "ecdsa_secp384r1_sha384",
    "ecdsa_secp521r1_sha512",
    "rsa_pss_rsae_sha256",
    "rsa_pss_rsae_sha384",
    "rsa_pss_rsae_sha512",
    "rsa_pkcs1_sha256",
    "rsa_pkcs1_sha384",
    "rsa_pkcs1_sha512",
    "ecdsa_sha1",
    "rsa_pkcs1_sha1",
]

PEET_URL = "https://tls.peet.ws/api/all"
TARGET_JA3_HASH = "6447ab086255d194909d4013b1a89e87"
TARGET_JA4 = "t13d1617h2_86a278354501_3cbfd9057e0d"


def main() -> None:
    out = {
        "target_ja3_hash": TARGET_JA3_HASH,
        "target_ja4": TARGET_JA4,
        "attempts": [],
    }

    # Próba 1: pełny własny fingerprint (ja3 + akamai + extra_fp)
    attempts = [
        {
            "name": "full_ja3_akamai_extra",
            "kw": {
                "ja3": FF152_JA3,
                "akamai": FF152_AKAMAI,
                "extra_fp": FF152_EXTRA_FP,
            },
        },
        {
            "name": "ja3_only",
            "kw": {"ja3": FF152_JA3},
        },
        {
            "name": "firefox147_builtin",
            "kw": {"impersonate": "firefox147"},
        },
        {
            "name": "extra_sigalgs",
            "kw": {
                "ja3": FF152_JA3,
                "akamai": FF152_AKAMAI,
                "extra_fp": {**FF152_EXTRA_FP, "tls_signature_algorithms": FF152_SIGALGS},
            },
        },
        {
            "name": "extra_sigalgs_nocertcomp",
            "kw": {
                "ja3": FF152_JA3,
                "akamai": FF152_AKAMAI,
                "extra_fp": {
                    "tls_delegated_credential": FF152_EXTRA_FP["tls_delegated_credential"],
                    "tls_record_size_limit": 16385,
                    "tls_signature_algorithms": FF152_SIGALGS,
                },
            },
        },
        {
            "name": "extra_sigalgs_permute",
            "kw": {
                "ja3": FF152_JA3,
                "akamai": FF152_AKAMAI,
                "extra_fp": {
                    **FF152_EXTRA_FP,
                    "tls_signature_algorithms": FF152_SIGALGS,
                    "tls_permute_extensions": True,
                },
            },
        },
        {
            "name": "extra_cert_zlib",
            "kw": {
                "ja3": FF152_JA3,
                "akamai": FF152_AKAMAI,
                "extra_fp": {**FF152_EXTRA_FP, "tls_cert_compression": "zlib"},
            },
        },
        {
            "name": "extra_cert_brotli",
            "kw": {
                "ja3": FF152_JA3,
                "akamai": FF152_AKAMAI,
                "extra_fp": {**FF152_EXTRA_FP, "tls_cert_compression": "brotli"},
            },
        },
    ]

    for attempt in attempts:
        name = attempt["name"]
        kw = attempt["kw"]
        row = {"name": name, "kw": kw}
        try:
            r = creq.get(PEET_URL, timeout=30, **kw)
            row["status"] = r.status_code
            if r.status_code == 200:
                data = r.json()
                tls = data.get("tls", {})
                row["ja3_hash"] = tls.get("ja3_hash")
                row["ja4"] = tls.get("ja4")
                row["ja3"] = tls.get("ja3")
                row["matched_ja3_hash"] = (
                    tls.get("ja3_hash") == TARGET_JA3_HASH
                )
                row["matched_ja4"] = tls.get("ja4") == TARGET_JA4
            else:
                row["body"] = r.text[:200]
        except Exception as exc:  # noqa: BLE001
            row["error"] = repr(exc)

        print(json.dumps(row, ensure_ascii=False, indent=2))
        out["attempts"].append(row)

    with open("wynik_curl_cffi_firefox152.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print("\nZapisano wynik do: wynik_curl_cffi_firefox152.json")


if __name__ == "__main__":
    main()