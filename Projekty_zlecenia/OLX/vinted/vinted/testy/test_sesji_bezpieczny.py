# coding: utf-8
"""BEZPIECZNY test sesji — TYLKO jeden odczyt profilu (GET users/me).
NIE dotyka checkoutu, rezerwacji ani płatności.
Cel: potwierdzić, że świeże cookies działają i sprawdzić tożsamość konta."""
import json
import http.cookiejar
from curl_cffi import requests as creq

IMP = "chrome124"
COOKIES = r"C:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\vinted\dane\cookies_fresh.txt"

jar = http.cookiejar.MozillaCookieJar(COOKIES)
jar.load(ignore_discard=True, ignore_expires=True)

def cookie_dict():
    return {c.name: c.value for c in jar}

s = creq.Session(impersonate=IMP)
s.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
    "Referer": "https://www.vinted.pl/",
    "Origin": "https://www.vinted.pl",
})

url = "https://www.vinted.pl/api/v2/users/current"
print("### Pojedynczy bezpieczny odczyt:", url)
try:
    r = s.get(url, cookies=cookie_dict(), timeout=20)
    print("STATUS:", r.status_code)
    print("FINAL URL:", r.url[:120])
    ct = r.headers.get("content-type", "")
    print("CONTENT-TYPE:", ct)
    for h in ["x-datadome", "x-datadome-isbot", "server", "cf-ray"]:
        if h in r.headers:
            print(f"  HEADER {h}: {r.headers[h]}")
    body = r.text
    print("BODY (first 800):", body[:800])
    if "application/json" in ct:
        try:
            j = r.json()
            if isinstance(j, dict):
                # nie wypisuj wrażliwych danych — tylko kluczowe pola
                safe = {k: j.get(k) for k in ["id", "login", "country_code", "country", "anon_id"] if k in j}
                print("BEZPIECZNE POLA:", json.dumps(safe, ensure_ascii=False))
        except Exception as e:
            print("JSON PARSE ERR:", e)
except Exception as e:
    print("EXCEPTION:", repr(e))