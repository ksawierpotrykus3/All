import re
from pathlib import Path

chunks_dir = Path("dane/chunks")
chunk_files = list(chunks_dir.glob("*.js"))

for f in chunk_files:
    content = f.read_text(encoding="utf-8", errors="ignore")
    if "purchases/checkout" in content or "fetchInitialSingleCheckout" in content or "initiateSingleCheckout" in content:
        print(f"\n========================================================")
        print(f"Plik: {f.name} (rozmiar: {len(content)} bajtów)")
        
        for m in re.finditer(r'(?:purchases/checkout|fetchInitialSingleCheckout|initiateSingleCheckout|refreshSingleCheckout|updateSingleCheckout)', content):
            start = max(0, m.start() - 150)
            end = min(len(content), m.end() + 250)
            print("--- KOD ---")
            print(content[start:end])
