# coding: utf-8
"""BEZPIECZNA weryfikacja wlasciciela przedmiotu 9782578256 przez publiczna strone SSR."""
import re
import json
import http.cookiejar
from curl_cffi import requests as creq

IMP = "chrome124"
COOKIES = r"C:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\vinted\dane\cookies_fresh.txt"
ITEM_URL = "https://www.vinted.pl/items/9782578256-zimowa-kurtka-bershka"

jar = http.cookiejar.MozillaCookieJar(COOKIES)
jar.load(ignore_discard=True, ignore_expires=True)

def cookie_dict():
    return {c.name: c.value for c in jar}

s = creq.Session(impersonate=IMP)
s.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
})

print("### GET publiczna strona:", ITEM_URL)
try:
    r = s.get(ITEM_URL, cookies=cookie_dict(), timeout=25)
    print("STATUS:", r.status_code)
    body = r.text
    print("DLUGOSC BODY:", len(body))
    # szukamy danych sprzedawcy w HTML/JSON
    # czeste wzorce: "user":{"id":NNN, "login":"xxx"  albo  member/IDN-login
    owner_hits = re.findall(r'member/(\d+)-([a-zA-Z0-9_]+)', body)
    print("MEMBER LINKS:", list(set(owner_hits))[:10])
    id_hits = re.findall(r'"user"\s*:\s*\{[^}]*"id"\s*:\s*(\d+)', body)
    print("USER ID HITS:", id_hits[:10])
    login_hits = re.findall(r'"login"\s*:\s*"([^"]+)"', body)
    print("LOGIN HITS:", list(set(login_hits))[:10])
    # czy strona zawiera w ogole ten item id
    print("CZY ZAWIERA 9782578256:", "9782578256" in body)
    # zapisz fragment wokol item id
    idx = body.find("9782578256")
    if idx >= 0:
        print("KONTEKST:", body[max(0, idx-200):idx+400][:600])
except Exception as e:
    print("EXCEPTION:", repr(e))