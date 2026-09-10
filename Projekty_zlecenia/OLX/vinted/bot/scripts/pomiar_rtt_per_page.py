# coding: utf-8
"""Pomiar RTT detekcji dla roznych per_page (wspoldzielona sesja keep-alive)."""
import json
import time
from vintedbot.models import Filtry, KonfiguracjaKonta
from vintedbot.detection import pobierz_oferty
from vintedbot.checkout import pobierz_sesje

ck = json.load(open("output/cookies_fresh.json", encoding="utf-8"))
s = pobierz_sesje(KonfiguracjaKonta(cookies=ck), "detekcja")

wyniki = {}
for n in (5, 10, 24, 48, 96):
    czasy = []
    for _ in range(4):
        t0 = time.monotonic()
        of = pobierz_oferty(Filtry(), limit=n, cookies=ck, session=s)
        czasy.append((time.monotonic() - t0) * 1000)
        time.sleep(1.2)  # rate-limit ~0.83 req/s
    czasy.sort()
    wyniki[n] = {"p50": czasy[1], "min": czasy[0], "max": czasy[3], "oferty": len(of)}
    print(f"per_page={n:>3}  p50={czasy[1]:>6.0f}ms  min={czasy[0]:>6.0f}ms  max={czasy[3]:>6.0f}ms")

out = "output/rtt_per_page.json"
with open(out, "w", encoding="utf-8") as fh:
    json.dump(wyniki, fh, ensure_ascii=False, indent=2)
print(f"zapisano -> {out}")
