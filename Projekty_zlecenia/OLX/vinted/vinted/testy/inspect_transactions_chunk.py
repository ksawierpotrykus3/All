import re
from pathlib import Path

chunks_dir = Path("dane/chunks")
chunk_files = list(chunks_dir.glob("*.js"))

for f in chunk_files:
    content = f.read_text(encoding="utf-8", errors="ignore")
    if "transactions" in content.lower() or "checkout" in content.lower() or "transaction" in content.lower():
        print(f"\n========================================================")
        print(f"Plik: {f.name} (rozmiar: {len(content)} bajtów)")
        
        # Extract surrounding context of 'transactions' or 'checkout'
        matches = [m.start() for m in re.finditer(r'(?:transactions|checkout|shipment|payment)', content, re.IGNORECASE)]
        print(f"Znaleziono {len(matches)} wystąpień słów kluczowych.")
        for idx in matches[:10]:
            start = max(0, idx - 100)
            end = min(len(content), idx + 150)
            print("--- Snippet ---")
            print(content[start:end].replace("\n", " "))
