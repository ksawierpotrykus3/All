# coding: utf-8
"""Szuka modulu useCreateConversation (485545) w chunkach."""
import re
from pathlib import Path

d = Path(__file__).resolve().parent / "chunks_har"
for fn in sorted(d.glob("*.js")):
    js = fn.read_text(encoding="utf-8", errors="replace")
    for m in list(re.finditer(r"485545", js)):
        s0 = max(0, m.start() - 400)
        print(f"[{fn.name}] 485545 @ {m.start()}")
        print(js[s0:m.end() + 2500].replace("\n", " ")[:2900])
        print()
