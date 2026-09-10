# coding: utf-8
"""_card_registrations_h4_test.py — test hipotezy H4.

H4: card_registrations NIE wymaga tokenu Incognia (udowodnione w APK) i moze
miec nizszy prog DataDome niz checkout/build -> moze przejsc 200 w curl_cffi.

Test:
  1. POST payments/public/api/card_registrations  (body: {"card_registration": null})
     -> oczekiwane 200 + access_key (wtedy mozna lokalnie szyfrowac karte Adyen CSE)

Jesli 200 -> H4 POTWIERDZONA (pre-tokenizacja karty mozliwa bez glownej blokady).
Jesli 403 -> H4 ODRZUCONA (DataDome blokuje rowniez card_registrations).
"""
import json
from pathlib import Path

from curl_cffi import requests as cr

COOKIES_FILE = Path(r"F:\PROJEKTY\vinted\vinted\testy_camoufox\docs\references\cookies_profil.json")
OUT_JSON = Path(r"F:\PROJEKTY\vinted\vinted\testy_camoufox\docs\logs\_card_registrations_h4.json")

CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

result = {"status": None, "ms": None, "body": None, "access_key_prefix": None,
          "card_registration_id": None, "provider": None, "error": None}


def log(m):
    print("[H4] " + m, flush=True)


def main():
    cookies = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))
    jar = {c["name"]: c["value"] for c in cookies if "vinted.pl" in c.get("domain", "")}
    log("cookies vinted.pl: %d" % len(jar))

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "locale": "pl-PL",
        "x-csrf-token": CSRF,
        "x-anon-id": ANON,
        "origin": "https://www.vinted.pl",
        "referer": "https://www.vinted.pl/",
    }

    try:
        import time
        t0 = time.monotonic()
        r = cr.post(
            "https://www.vinted.pl/api/v2/payments/public/api/card_registrations",
            data=json.dumps({"card_registration": None}),
            headers=headers,
            cookies=jar,
            impersonate="chrome124",
            timeout=30,
        )
        result["ms"] = round((time.monotonic() - t0) * 1000)
        result["status"] = r.status_code
        log("POST card_registrations: %d ms status=%d" % (result["ms"], r.status_code))
        body = r.text
        result["body"] = body[:600]
        if r.status_code == 200:
            try:
                j = r.json()
                # wyciagnij kluczowe pola niezaleznie od struktury
                def find(obj, keys, path=""):
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            if k in keys:
                                yield path + "/" + k, v
                            yield from find(v, keys, path + "/" + k)
                    elif isinstance(obj, list):
                        for i, v in enumerate(obj):
                            yield from find(v, keys, path + "/%d" % i)
                hits = dict(find(j, {"access_key", "card_registration_id", "provider", "id"}))
                if "access_key" in str(hits):
                    for k, v in hits.items():
                        if k.endswith("access_key"):
                            result["access_key_prefix"] = str(v)[:30] + "... (len=%d)" % len(str(v))
                        if k.endswith("card_registration_id") or k.endswith("/id"):
                            result["card_registration_id"] = v
                        if k.endswith("provider"):
                            result["provider"] = v
                log("200 OK: %s" % json.dumps({k: (str(v)[:40]) for k, v in hits.items()}, ensure_ascii=False))
            except Exception as e:
                log("parse body fail: %r" % e)
        else:
            log("status %d, body: %s" % (r.status_code, body[:300]))
    except Exception as e:
        result["error"] = repr(e)
        log("FAIL: %r" % e)

    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    log("SAVED -> " + str(OUT_JSON))


if __name__ == "__main__":
    main()
