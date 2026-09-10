# coding: utf-8
"""Szuka w HTML item page: 'Buy now' przycisk/endpoint, dane transakcji, escrow init."""
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
html = (BASE_DIR / "item_page_live.html").read_text(encoding="utf-8")

# 1) Poszukaj 'buy' w kontekście (przycisk, link)
print("### kontekst 'Buy now' / buy button:")
for m in list(re.finditer(r"buy[^<>]{0,80}", html, re.IGNORECASE))[:20]:
    s = max(0, m.start() - 120)
    print("   ..." + html[s:m.end() + 120].replace("\n", " ")[:240] + "...")
    print("   " + "-"*60)

# 2) Szukaj 'transaction' w kontekście danych (SSR JSON)
print("\n### 'transaction_id' / 'transactionId':")
for m in list(re.finditer(r"transaction[_i]?[dD]?[^\"']{0,30}", html))[:10]:
    s = max(0, m.start() - 100)
    print("   ..." + html[s:m.end() + 100].replace("\n", " ")[:220] + "...")
    print("   " + "-"*60)
