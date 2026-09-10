# coding: utf-8
"""Znajdz 'pickup_point_code' / 'pickup_details' w chunkach JS."""
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent / "chunks_har"
patterns = ["pickup_point_code", "pickup_details", "selected_rate_uuid", "rate_uuid"]
for f in sorted(BASE.glob("*.js")):
    txt = f.read_text(encoding="utf-8", errors="ignore")
    for pat in patterns:
        if pat in txt:
            print(f"===== {f.name} contains {pat} =====")
            for m in re.finditer(re.escape(pat), txt):
                s = max(0, m.start() - 200)
                e = min(len(txt), m.end() + 200)
                print("---")
                print(txt[s:e])
                break  # tylko pierwszy kontekst na plik
