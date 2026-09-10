# coding: utf-8
"""Szybki test: czy 403 to staly rate-limit, czy chwilowy incydent. 100 zapytan."""
from curl_cffi import requests as creq
import collections

IMP = "chrome124"
API = "https://www.olx.pl/api/v1/offers/"
start = 1093574000

codes = collections.Counter()
for i in range(100):
    try:
        r = creq.get(API + str(start + i) + "/", impersonate=IMP, timeout=10)
        codes[r.status_code] += 1
    except Exception as e:
        codes[-1] += 1

print(dict(codes))