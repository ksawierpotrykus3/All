import re
from pathlib import Path

chunks_dir = Path("dane/chunks")
chunk_files = list(chunks_dir.glob("*.js"))

for f in chunk_files:
    content = f.read_text(encoding="utf-8", errors="ignore")
    # Search for api.post or t.api.post or api.put
    posts = re.findall(r'(?:api\.post|api\.put|api\.get|api\.delete)\([^\)]+\)', content)
    if posts:
        print(f"\n========================================================")
        print(f"Plik: {f.name} - Znaleziono {len(posts)} wywołań api:")
        for p in set(posts):
            print("  API call:", p[:120])
