"""Sprawdzenie konkretnie POST /checkout/build - request + response szczegolowo."""
import json
from urllib.parse import urlparse

d = json.load(open(r"C:\Temp\wynik_spike_F1_real_firefox.json", encoding="utf-8"))

# Szukamy POST /checkout/build
for req in d["all_requests"]:
    if "/api/v2/purchases/checkout/build" in req["url"] and req["method"] == "POST":
        print("REQUEST:")
        print(json.dumps(req, indent=2, ensure_ascii=False))
        break

print("\n" + "=" * 80)

# Szukamy odpowiedzi
for resp in d["responses"]:
    if "/api/v2/purchases/checkout/build" in resp["url"]:
        print(f"\nRESPONSE {resp['status']}:")
        print(f"URL: {resp['url']}")
        print(f"Headers (selected):")
        for k, v in resp["headers"].items():
            if any(s in k.lower() for s in ("datadome", "incognia", "csrf", "x-anon",
                                              "set-cookie", "content-type", "vary",
                                              "x-frame", "permissions", "x-request")):
                print(f"  {k}: {v[:200]}")
        print(f"All headers count: {len(resp['headers'])}")
        break

# Sprawdź czy POST miał header Incognia - niestety Playwright nie zwraca naglowkow POST
# Ale mozemy zobaczyc czy cookies maja cos zwiazanego z Incognia
print("\n" + "=" * 80)
print("Sprawdzenie cookies sesyjnych Vinted (Incognia headers):")
cookies_have = [k for k in resp["headers"].keys() if "incognia" in k.lower()]
print(f"  Naglowki z 'incognia': {cookies_have}")
