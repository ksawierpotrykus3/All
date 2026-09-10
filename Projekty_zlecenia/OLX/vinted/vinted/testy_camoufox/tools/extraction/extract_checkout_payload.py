# coding: utf-8
"""Wyciaga krotkie fragmenty wokol terminow checkoutu i zapisuje do czytelnego pliku."""
from pathlib import Path

CHUNK = Path(r"f:\PROJEKTY\vinted\vinted\dane\chunks\0~~ak8p40jr.6.js")
OUT = Path(r"f:\PROJEKTY\vinted\vinted\testy_camoufox\checkout_payload_extract.txt")

TERMS = [
    "initiateSingleCheckout",
    "updateSingleCheckoutData",
    "fetchInitialSingleCheckoutData",
    "refreshSingleCheckoutPurchase",
    "purchase_items",
    "shipping_pickup_details",
    "payment_method",
    "rate_uuid",
    "point_code",
    "point_uuid",
    "GO_TO_WALLET_URL",
]
PRE = 250
POST = 350

text = CHUNK.read_text(encoding="utf-8", errors="ignore")
out_lines = [f"Analiza chunku: {CHUNK.name}", f"Dlugosc: {len(text)} znakow", "=" * 80]

for term in TERMS:
    positions = []
    idx = 0
    while True:
        idx = text.find(term, idx)
        if idx == -1:
            break
        positions.append(idx)
        idx += len(term)
    out_lines.append(f"\n#### {term} — {len(positions)} wystapien ####")
    for p in positions[:5]:
        s = max(0, p - PRE)
        e = min(len(text), p + POST)
        frag = text[s:e].replace("\n", " ").replace("\r", " ")
        out_lines.append(f"  @{p}: ...{frag}...")
    if len(positions) > 5:
        out_lines.append(f"  ... (ucieto, lacznie {len(positions)} wystapien)")

OUT.write_text("\n".join(out_lines), encoding="utf-8")
print(f"Zapisano do: {OUT}")
print(f"Liczba linii: {len(out_lines)}")