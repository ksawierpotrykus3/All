# coding: utf-8
"""Szukamy w chunkach JS endpointow delete/remove/cancel dot. konwersacji/inquiries."""
import re
import glob
import io

pat = re.compile(r"(delete|remove|cancel|destroy|close)[A-Za-z]*\([^)]*?(conversation|inquir|thread)", re.I)
for f in glob.glob("chunks_har/*.js"):
    try:
        s = io.open(f, encoding="utf-8", errors="ignore").read()
    except Exception:
        continue
    for m in pat.finditer(s):
        seg = s[max(0, m.start() - 160): m.start() + 260]
        print(f.split("\\")[-1], "::", seg[:420])
        print("---")
