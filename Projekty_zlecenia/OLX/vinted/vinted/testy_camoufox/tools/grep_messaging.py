# coding: utf-8
"""Szukaj w chunkach: messaging/main endpoints + inquiry delete/cancel."""
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent / "chunks_har"
out = []
for f in sorted(BASE.glob("*.js")):
    txt = f.read_text(encoding="utf-8", errors="ignore")
    for pat in ["messaging/main", "/inquiries", "inquiries", "cancel", "delete"]:
        for m in re.finditer(re.escape(pat), txt):
            s = max(0, m.start() - 200)
            e = min(len(txt), m.end() + 200)
            ctx = txt[s:e]
            if "inquir" in pat or "messaging" in pat or ("cancel" in pat and ("transaction" in ctx or "inquir" in ctx)):
                out.append(f"===== {f.name} [{pat}] =====")
                out.append(ctx)
                out.append("")
            break

Path(__file__).resolve().parent.joinpath("grep_messaging_out.txt").write_text(
    "\n".join(out), encoding="utf-8")
print("OK -> grep_messaging_out.txt")
