# coding: utf-8
"""Sprawdza wlasciciela przedmiotu testowego z HTML SSR (bez logowania)."""
import re
import urllib.request

ITEM_URL = "https://www.vinted.pl/items/9806080522-test123"

req = urllib.request.Request(ITEM_URL, headers={"User-Agent": "Mozilla/5.0"})
body = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")

print("LEN:", len(body))

member_hits = re.findall(r"member/(\d+)-([a-zA-Z0-9_]+)", body)
print("MEMBER LINKS:", list(set(member_hits))[:10])

# JSON-LD: szukamy pola seller/identifier lub author
ident = re.findall(r'"identifier"\s*:\s*"?(\d+)"?', body)
print("IDENTIFIERS:", list(set(ident))[:10])

user_hits = re.findall(r'"login"\s*:\s*"([^"]+)"', body)
print("LOGINS:", list(set(user_hits))[:10])

# tytul
t = re.search(r"<title>([^<]+)</title>", body)
print("TITLE:", t.group(1) if t else "?")