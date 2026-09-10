# coding: utf-8
"""Dokladne sprawdzenie wlasciciela przedmiotu testowego - analiza surowego HTML SSR."""
import re
import urllib.request

ITEM_URL = "https://www.vinted.pl/items/9806080522-test123"
req = urllib.request.Request(ITEM_URL, headers={"User-Agent": "Mozilla/5.0"})
body = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")

# szukaj wszelkich ID uzytkownikow i loginow w roznych formatach
patterns = [
    r'"user_id"\s*:\s*"?(\d+)"?',
    r'"user"\s*:\s*\{\s*"id"\s*:\s*(\d+)',
    r'"seller_id"\s*:\s*"?(\d+)"?',
    r'"owner_id"\s*:\s*"?(\d+)"?',
    r'member/(\d+)',
    r'"login"\s*:\s*"([^"]+)"',
    r'"username"\s*:\s*"([^"]+)"',
    r'maksks0',
    r'3180346878',
]
for p in patterns:
    hits = list(set(re.findall(p, body)))
    if hits:
        print(f"{p}  ->  {hits[:10]}")
    else:
        print(f"{p}  ->  BRAK")

# fragment wokol 'maksks0' lub '3180346878' gdyby byl
for token in ["maksks0", "3180346878", "test123"]:
    i = body.find(token)
    if i != -1:
        print(f"\n--- kontekst '{token}' @ {i} ---")
        print(body[max(0,i-200):i+300].replace("\n"," ")[:500])