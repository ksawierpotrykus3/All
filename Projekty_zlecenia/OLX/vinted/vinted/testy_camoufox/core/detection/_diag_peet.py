# coding: utf-8
"""Porównanie peetprint prawdziwego FF152 vs curl_cffi custom FF152 (tls.peet.ws)."""
import json
from curl_cffi import requests as cr

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
    "tls_signature_algorithms": [
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
    ],
}

TARGET_PEETPRINT = "fd4547eeb41f073156b7bc8125a79a3c"  # prawdziwy FF152 z wynik_ja3_firefox152.json

r = cr.get("https://tls.peet.ws/api/all",
           ja3=FF152_JA3, akamai=FF152_AKAMAI, extra_fp=FF152_EXTRA_FP, timeout=30)
d = r.json()
tls = d.get("tls", {})
http2 = d.get("http2", {})

print("ja3_hash   :", tls.get("ja3_hash"))
print("ja4        :", tls.get("ja4"))
print("peetprint  :", tls.get("peetprint"))
print("peet_hash  :", tls.get("peetprint_hash"), "MATCH" if tls.get("peetprint_hash") == TARGET_PEETPRINT else "MISMATCH (cel " + TARGET_PEETPRINT + ")")
print("akamai     :", http2.get("akamai_fingerprint"))
print("akamai_hash:", http2.get("akamai_fingerprint_hash"))