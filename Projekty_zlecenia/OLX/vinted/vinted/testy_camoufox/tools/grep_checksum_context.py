# coding: utf-8
"""Znajdz kontekst wokol 'checksum' w chunkach JS."""
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent / "chunks_har"
for f in ["0m6z-r2_~i3np.js", "0p3.vfb7uddnl.js"]:
    txt = (BASE / f).read_text(encoding="utf-8", errors="ignore")
    print(f"===== {f} =====")
    for m in re.finditer(r"checksum", txt):
        s = max(0, m.start() - 350)
        e = min(len(txt), m.end() + 350)
        print("---")
        print(txt[s:e])
    print()
