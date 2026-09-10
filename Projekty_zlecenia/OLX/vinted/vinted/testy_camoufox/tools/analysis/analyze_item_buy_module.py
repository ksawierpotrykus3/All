# coding: utf-8
"""Analizuje modul strony itemu: 09sviqj9zkjl0.js - handler Kup teraz."""
from pathlib import Path

js = Path("chunks_har/09sviqj9zkjl0.js").read_text(encoding="utf-8", errors="replace")
print(f"LEN: {len(js)}")

# Kontekst wokol useNavigateToCheckout
i = js.find("useNavigateToCheckout")
print("=" * 80)
print("### KONTEKST useNavigateToCheckout (4000 przed, 4000 po) ###")
print(js[max(0, i - 4000):i + 4000])
