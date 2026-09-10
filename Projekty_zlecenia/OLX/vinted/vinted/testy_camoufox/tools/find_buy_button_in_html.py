# coding: utf-8
"""Wyciaga kontekst wokol przycisku Kup teraz / buy z item_page_live.html."""
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
HTML = (BASE_DIR / "item_page_live.html").read_text(encoding="utf-8", errors="replace")
print(f"HTML len: {len(HTML)}")

# Szukamy tekstow przycisku
for kw in ["Kup teraz", "Kup teraz za", "buy_now", "Buy now", "transaction", "button", "aria-label"]:
    for m in list(re.finditer(re.escape(kw), HTML))[:5]:
        s0 = max(0, m.start() - 200)
        frag = HTML[s0:m.end() + 250].replace("\n", " ")
        print(f"\n--- {kw} @ {m.start()} ---")
        print(frag[:450])
