# coding: utf-8
"""TEST REZERWACJI (checkout/build) na WŁASNYM przedmiocie 9782578256.
NIE wysyla platnosci. Tylko POST /purchases/checkout/build (rezerwacja).
Przedmiot nalezy do konta konto_A (id 111111111) - potwierdzone przez SSR HTML."""
import json
import http.cookiejar
from curl_cffi import requests as creq

IMP = "chrome124"
COOKIES = r"C:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\vinted\dane\cookies_fresh.txt"
ITEM_ID = 9782578256

jar = http.cookiejar.MozillaCookieJar(COOKIES)
jar.load(ignore_discard=True, ignore_expires=True)

def cookie_dict():
    return {c.name: c.value for c in jar}

s = creq.Session(impersonate=IMP)
s.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
    "Referer": f"https://www.vinted.pl/items/{ITEM_ID}",
    "Origin": "https://www.vinted.pl",
    "Content-Type": "application/json",
})

url = "https://www.vinted.pl/api/v2/purchases/checkout/build"
payload = {"purchase_items": [{"id": ITEM_ID, "type": "item"}]}

print("### POST", url)
print("### PAYLOAD:", json.dumps(payload, ensure_ascii=False))
print("### UWAGA: to REZERWACJA, NIE platnosc. Bez tego nie bedzie transakcji.")
try:
    r = s.post(url, cookies=cookie_dict(), json=payload, timeout=25)
    print("STATUS:", r.status_code)
    print("FINAL URL:", r.url[:150])
    ct = r.headers.get("content-type", "")
    print("CONTENT-TYPE:", ct)
    for h in ["x-datadome", "x-datadome-isbot", "server", "cf-ray", "location"]:
        if h in r.headers:
            print(f"  HEADER {h}: {r.headers[h]}")
    body = r.text
    print("BODY (first 1500):", body[:1500])
    # proba zapisu surowej odpowiedzi
    with open(r"C:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\vinted\dane\odpowiedz_checkout_build.json", "w", encoding="utf-8") as f:
        f.write(body)
    print(">>> Zapisano surowa odpowiedz do: dane/odpowiedz_checkout_build.json")
except Exception as e:
    print("EXCEPTION:", repr(e))