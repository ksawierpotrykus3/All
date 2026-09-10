# coding: utf-8
"""Zbadaj naglowki i cialo cchd_config z vinted.har — co to za JWT?

Bez ruchu na zywo. Cel: ustalic, czy JWT z cchd_config zawiera w payloadzie
klucz publiczny RSA (bo mime=application/jwt, a nie surowy klucz).
"""
import json
import base64
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
HAR = BASE_DIR / "vinted.har"

TARGET = "cchd_config"


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def main() -> None:
    data = json.loads(HAR.read_text(encoding="utf-8", errors="replace"))
    entries = data.get("log", {}).get("entries", [])

    for e in entries:
        url = e.get("request", {}).get("url", "")
        if TARGET not in url:
            continue
        resp = e.get("response", {})
        print("=" * 70)
        print("URL:", url)
        print("STATUS:", resp.get("status"))

        # Nagłówki odpowiedzi — szukaj content-type, set-cookie, etc.
        print("-- response headers --")
        for h in resp.get("headers", []):
            n = h.get("name", "").lower()
            if n in ("content-type", "set-cookie", "cache-control", "x-", "content-length"):
                print(f"  {h.get('name')}: {h.get('value')}")

        # Ciało — czy jest base64 czy raw
        content = resp.get("content", {})
        enc = content.get("encoding")
        raw = content.get("text", "")
        print(f"-- content: mime={content.get('mimeType')} size={content.get('size')} encoding={enc} --")
        if raw:
            body = raw
            if enc == "base64":
                try:
                    body = base64.b64decode(raw).decode("utf-8", errors="replace")
                except Exception as exc:  # noqa: BLE001
                    body = f"<b64 err {exc}>"
            # JWT = header.payload.signature
            if body.count(".") == 2:
                h, p, s = body.split(".")
                try:
                    print("JWT header:", _b64url_decode(h).decode("utf-8", "replace"))
                    print("JWT payload:", _b64url_decode(p).decode("utf-8", "replace"))
                    print("JWT signature len:", len(s))
                except Exception as exc:  # noqa: BLE001
                    print("JWT decode err:", exc)
                print("JWT raw body:", body[:800])
            else:
                print("BODY:", body[:800])
        else:
            print("  <brak ciała w HAR>")
        print()


if __name__ == "__main__":
    main()