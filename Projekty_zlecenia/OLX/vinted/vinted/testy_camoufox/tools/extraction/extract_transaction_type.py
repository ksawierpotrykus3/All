# coding: utf-8
"""Wyciaga kontekst wokol 'type:"transaction"', 'type:"item"' i 'transaction_id' w chunkach."""
from pathlib import Path

CHUNKS = Path(r"f:\PROJEKTY\vinted\vinted\dane\chunks")
OUT = Path(r"f:\PROJEKTY\vinted\vinted\testy_camoufox\transaction_type_extract.txt")
FILES = [
    "15ftf8g1vmdwu.js",
    "0~~ak8p40jr.6.js",
    "0~ptmgk141av1.js",
    "0slgj5ozfhb0t.js",
    "0jq7wv_8d~c3p.js",
    "0fsh1_qbrfm3l.js",
    "0.53ezhi8oq8t.js",
]
TERMS = ['type:"transaction"', 'type:"item"', '"transaction"', 'transaction_id', 'transactionId', 'orderType', 'order_type']
PRE = 300
POST = 400

out_lines = []
for name in FILES:
    p = CHUNKS / name
    text = p.read_text(encoding="utf-8", errors="ignore")
    out_lines.append(f"\n{'='*70}\n### {name} (len={len(text)})\n{'='*70}")
    for term in TERMS:
        idx = 0
        positions = []
        while True:
            idx = text.find(term, idx)
            if idx == -1:
                break
            positions.append(idx)
            idx += len(term)
        if not positions:
            continue
        out_lines.append(f"\n--- {term}: {len(positions)} wystapien ---")
        for pos in positions[:6]:
            s = max(0, pos - PRE)
            e = min(len(text), pos + POST)
            frag = text[s:e].replace("\n", " ").replace("\r", " ")
            out_lines.append(f"  @{pos}: ...{frag}...")

OUT.write_text("\n".join(out_lines), encoding="utf-8")
print(f"Zapisano do: {OUT}")
print(f"Linii: {len(out_lines)}")