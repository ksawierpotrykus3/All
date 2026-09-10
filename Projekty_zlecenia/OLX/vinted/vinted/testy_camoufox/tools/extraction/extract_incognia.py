# coding: utf-8
"""Wyciaga fragmenty wokol 'incognia' ze wszystkich chunkow, ktore go zawieraja."""
from pathlib import Path

CHUNKS_DIR = Path(r"f:\PROJEKTY\vinted\vinted\dane\chunks")
OUT = Path(r"f:\PROJEKTY\vinted\vinted\testy_camoufox\incognia_extract.txt")
FILES = [
    "12ngissau-92c.js",
    "12ix5tzmok~f9.js",
    "0~~ak8p40jr.6.js",
    "0~ptmgk141av1.js",
    "0hxc25fbtbsy4.js",
]
TERM = "incognia"
PRE = 400
POST = 500

out_lines = []
for name in FILES:
    p = CHUNKS_DIR / name
    if not p.exists():
        out_lines.append(f"\n### {name}: BRAK PLIKU")
        continue
    text = p.read_text(encoding="utf-8", errors="ignore")
    out_lines.append(f"\n### {name} (len={len(text)})")
    idx = 0
    count = 0
    while True:
        idx = text.lower().find(TERM, idx)
        if idx == -1:
            break
        s = max(0, idx - PRE)
        e = min(len(text), idx + POST)
        frag = text[s:e].replace("\n", " ").replace("\r", " ")
        out_lines.append(f"  @{idx}: ...{frag}...")
        idx += len(TERM)
        count += 1
        if count >= 6:
            break
    if count == 0:
        out_lines.append("  BRAK wystapien")

OUT.write_text("\n".join(out_lines), encoding="utf-8")
print(f"Zapisano do: {OUT}")