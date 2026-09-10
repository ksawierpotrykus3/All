# coding: utf-8
"""Identyfikacja konta klienta (v_uid 222222222) - bezpieczny odczyt GET users/current."""
import json
import http.cookiejar
from curl_cffi import requests as creq

IMP = "chrome124"
COOKIES = r"C:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\vinted\dane\cookies_klient.txt"

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
print("### GET", url)
try:
    r = s.get(url, cookies=cookie_dict(), timeout=20)
    print("STATUS:", r.status_code)
    body = r.text
    print("BODY (first 600):", body[:600])
    if r.status_code == 200:
        try:
            j = r.json()
            u = j.get("user", {})
            print("ID:", u.get("id"))
            print("LOGIN:", u.get("login"))
        except Exception as e:
            print("PARSE ERR:", e)
except Exception as e:
    print("EXCEPTION:", repr(e))