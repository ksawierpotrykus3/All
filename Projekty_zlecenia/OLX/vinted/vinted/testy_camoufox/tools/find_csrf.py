# coding: utf-8
"""Wyciaga okno tekstu wokol wystapien 'csrf'/'xsrf' w zminifikowanych chunkach JS."""
import re
from pathlib import Path

CHUNKS = Path(r"f:\PROJEKTY\vinted\vinted\dane\chunks")
FILES = ["15i-yotp89xhz.js", "15ftf8g1vmdwu.js", "0rp0mwndjqq50.js", "0m2hnd-95hk0v.js"]
PAT = re.compile(r"csrf|xsrf|anti-?forgery|x-money-padding", re.IGNORECASE)
WINDOW = 260

for name in FILES:
    p = CHUNKS / name
    if not p.exists():
        print(f"=== {name}: BRAK PLIKU ===")
        continue
    text = p.read_text(encoding="utf-8", errors="ignore")
    print(f"\n########## {name} (len={len(text)}) ##########")
    shown = 0
    for m in PAT.finditer(text):
        s = max(0, m.start() - WINDOW)
        e = min(len(text), m.end() + WINDOW)
        print(f"\n--- wystapienie @ {m.start()} ---")
        print(text[s:e])
        shown += 1
        if shown >= 5:
            print("... (ucieto do 5 wystapien)")
            break