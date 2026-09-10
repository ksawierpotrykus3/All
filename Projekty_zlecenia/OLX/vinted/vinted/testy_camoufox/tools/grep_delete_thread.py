# coding: utf-8
"""Znajdz w chunkach JS: delete_thread / usuwanie watku / konwersacji."""
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent / "chunks_har"
out = []
for f in sorted(BASE.glob("*.js")):
    txt = f.read_text(encoding="utf-8", errors="ignore")
    for pat in ["delete_thread", "deleteThread", "delete_thread", "conversations/"]:
        for m in re.finditer(re.escape(pat), txt):
            s = max(0, m.start() - 250)
            e = min(len(txt), m.end() + 250)
            out.append(f"===== {f.name} [{pat}] =====")
            out.append(txt[s:e])
            out.append("")
            break

Path(__file__).resolve().parent.joinpath("grep_delete_thread_out.txt").write_text(
    "\n".join(out), encoding="utf-8")
print("OK -> grep_delete_thread_out.txt")
