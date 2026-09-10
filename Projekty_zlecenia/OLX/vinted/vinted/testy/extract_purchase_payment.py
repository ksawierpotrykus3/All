import re
from pathlib import Path

chunks_dir = Path("dane/chunks")
chunk_files = list(chunks_dir.glob("*.js"))

for f in chunk_files:
    content = f.read_text(encoding="utf-8", errors="ignore")
    if "purchases" in content and ("pay" in content or "confirm" in content or "create" in content):
        print(f"\n========================================================")
        print(f"Plik: {f.name} (rozmiar: {len(content)} bajtów)")
        
        matches = [m.start() for m in re.finditer(r'/purchases/[^\'"`]+', content)]
        print(f"Znaleziono {len(matches)} wystąpień /purchases/...")
        for idx in matches:
            start = max(0, idx - 80)
            end = min(len(content), idx + 180)
            print("--- KOD ---")
            print(content[start:end])
