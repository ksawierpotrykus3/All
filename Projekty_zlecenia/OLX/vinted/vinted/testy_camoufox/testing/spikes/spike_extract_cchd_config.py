# coding: utf-8
"""Wyciagnij odpowiedz metrics.vinted.lt/web/cchd_config z vinted.har.

Bez ruchu na zywo — czysta analiza istniejacego HAR. Cel: sprawdzic, czy
endpoint konfiguracyjny Incognia zwraca klucz publiczny RSA (lub inny
material kryptograficzny) potrzebny do wygenerowania x-incognia-request-token.
"""
import json
import base64
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
HAR = BASE_DIR / "vinted.har"
OUT = BASE_DIR / "wynik_cchd_config_har.json"

TARGETS = [
    "https://metrics.vinted.lt/web/cchd_config",
    "https://metrics.vinted.lt/web/pvt_cchd_config",
]


def main() -> None:
    data = json.loads(HAR.read_text(encoding="utf-8", errors="replace"))
    entries = data.get("log", {}).get("entries", [])
    print(f"Entries: {len(entries)}")

    found = []
    for e in entries:
        url = e.get("request", {}).get("url", "")
        if any(t in url for t in TARGETS):
            resp = e.get("response", {})
            content = resp.get("content", {})
            status = resp.get("status")

            # HAR encode ciala: base64 lub raw text
            text = content.get("text", "")
            encoding = content.get("encoding")
            if encoding == "base64" and content.get("text"):
                try:
                    text = base64.b64decode(content["text"]).decode("utf-8", errors="replace")
                except Exception as exc:  # noqa: BLE001
                    text = f"<base64 decode error: {exc}>"

            record = {
                "url": url,
                "status": status,
                "mimeType": content.get("mimeType"),
                "size": content.get("size"),
                "body": text[:3000],
            }
            found.append(record)

            # Probe: czy cialo zawiera klucz RSA lub JWK
            lowered = text.lower()
            record["has_rsa_pem"] = "BEGIN PUBLIC KEY" in text or "BEGIN RSA PUBLIC KEY" in text
            record["has_jwk"] = '"kty"' in lowered
            record["has_modulus"] = '"n"' in lowered
            record["has_certificate"] = "BEGIN CERTIFICATE" in text

    result = {"count": len(found), "records": found}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    for r in found:
        print("=" * 60)
        print(f"URL: {r['url']}")
        print(f"status={r['status']} mime={r['mimeType']} size={r['size']}")
        print(f"RSA_PEM={r['has_rsa_pem']} JWK={r['has_jwk']} MODULUS={r['has_modulus']} CERT={r['has_certificate']}")
        print("BODY:", r["body"][:600])

    print(f"\nZapisano: {OUT}")


if __name__ == "__main__":
    main()