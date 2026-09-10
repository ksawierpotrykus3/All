# coding: utf-8
"""Analiza wzorca botowego: ile requestow na minute wysylamy do Vinted?"""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent

# Udane przebiegi (przed blokada)
udane = [
    ("test_rez_fresh_full", "2026-08-30T06:12:13", ["conversations", "build", "put_payment_method", "pickup_points", "put_pickup_details", "payment", "txn_status"]),
    ("bench_gateway run1", "2026-08-30T04:23:07", ["katalog", "conversations", "build", "put_pm", "pickup", "put_pickup", "payment", "txn", "camoufox_start", "camoufox_screenshot"]),
    ("bench_gateway seria1", "2026-08-30T04:28:xx", ["katalog", "conversations", "build", "put_pm", "pickup", "put_pickup", "payment", "txn"]),
    ("bench_gateway seria2", "2026-08-30T04:31:xx", ["katalog", "conversations", "build", "put_pm", "pickup", "put_pickup", "payment", "txn"]),
]

# Nieudane (po blokadzie)
nieudane = [
    ("bench_gateway seria3", "2026-08-30T04:33:xx", ["katalog", "conversations", "build(403)", "put_pm(404)", "put_pickup(404)", "payment(403)"]),
    ("test_hybryda", "2026-08-30T04:46:xx", ["camoufox", "katalog", "conversations", "build(403)"]),
    ("test_hybryda_v2", "2026-08-30T04:52:xx", ["camoufox", "katalog", "conversations", "build(403)"]),
    ("debug_build", "2026-08-30T04:51:xx", ["katalog", "conversations", "build(403)"]),
    ("test_reset_playwright", "2026-08-30T04:57:xx", ["playwright", "katalog", "conversations", "build(403)"]),
]

print("=== WZORZEC REQUESTOW ===")
print("\nUDANE (przed blokada):")
for name, ts, steps in udane:
    print(f"  {name} @ {ts}: {len(steps)} krokow")

print("\nNIEUDANE (po blokadzie):")
for name, ts, steps in nieudane:
    print(f"  {name} @ {ts}: {len(steps)} krokow")

# Kluczowa roznica: w udanych byly DLUGIE przerwy miedzy requestami
# (sleep 0.3-0.5s + processing), w nieudanych - krotkie lub zadne.
print("\n=== KLUCZOWA ROZNICA ===")
print("Udane: sleep 0.3-0.5s miedzy krokami + czas na przetwarzanie JSON")
print("Nieudane: requesty ida jeden za drugim bez przerwy (bot pattern)")
print("\nDodatkowo: w nieudanych bylo DUZO requestow w krotkim czasie")
print("(4 pelne flow w ~10 min = ~20 requestow zakupowych)")
