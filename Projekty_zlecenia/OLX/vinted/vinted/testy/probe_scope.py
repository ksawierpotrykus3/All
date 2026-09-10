# coding: utf-8
"""Sonda zakresu: max per_page + HTML strony itemu. READ-ONLY, wolne tempo."""
import json, time, http.cookiejar, re
from curl_cffi import requests as creq

jar = http.cookiejar.MozillaCookieJar(r"c:\Users\Ksawier\Pictures\Screenshots\Projekty_zlecenia\OLX\vinted\cookies.txt")
jar.load(ignore_discard=True, ignore_expires=True)
def cookie_dict():
    return {c.name: c.value for c in jar}

s = creq.Session(impersonate="chrome124")
s.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
    "Referer": "https://www.vinted.pl/",
    "Origin": "https://www.vinted.pl",
})

SLEEP = 1.5

# 1) max per_page
print("=== MAX PER_PAGE TEST ===")
best = None
for pp in [20, 96, 200, 500]:
    url = f"https://www.vinted.pl/api/v2/catalog/items?page=1&per_page={pp}&order=newest_first"
    r = s.get(url, cookies=cookie_dict(), timeout=25)
    n = len(r.json().get("items", [])) if r.status_code == 200 else -1
    print(f"per_page={pp}: status={r.status_code}, items={n}")
    if r.status_code == 200 and n > 0:
        best = {"pp": pp, "n": n, "j": r.json()}
    if r.status_code != 200:
        break
    time.sleep(SLEEP)

# 2) HTML strony itemu
print("\n=== HTML ITEM PAGE TEST ===")
if best:
    item = best["j"]["items"][0]
    iid = item["id"]
    # url strony - spróbujmy typowy wzorzec
    for cand in [
        f"https://www.vinted.pl/items/{iid}",
    ]:
        r = s.get(cand, cookies=cookie_dict(), timeout=25, allow_redirects=True)
        ct = r.headers.get("content-type", "")
        has_desc = "description" in r.text.lower() or "item" in r.text.lower()
        # wyciągnij tytuł z HTML jako sygnał poprawności
        m = re.search(r"<title>(.*?)</title>", r.text, re.S)
        title = m.group(1).strip()[:80] if m else "(brak)"
        print(f"URL {cand[:60]}: status={r.status_code}, CT={ct[:40]}, title={title!r}")
        # szukaj cechy danych (meta / json-ld)
        print("  JSON-LD obecny:", "application/ld+json" in r.text or "schema.org" in r.text)
        print("  BODY len:", len(r.text))
        time.sleep(SLEEP)
else:
    print("BRAK itemu z katalogu - nie testuje HTML")