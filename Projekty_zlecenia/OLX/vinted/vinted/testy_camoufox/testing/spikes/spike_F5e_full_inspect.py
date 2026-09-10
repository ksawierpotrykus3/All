"""F5e: Pełna inspekcja HAR pod kątem:
  1. Pełne request body do POST /connectioncheck
  2. Pełne response z POST /connectioncheck + GET /netconn (content może być binary)
  3. Wszystkie nagłówki w sekwencji auth Incognia
  4. Wszystkie entries z 'cookie' w response Set-Cookie (może tam jest klucz)
  5. Sprawdzenie content z wszystkich HTML responses > 10KB pod kątem inline scripts
"""
from __future__ import annotations

import json
import re
import base64
from pathlib import Path

HAR = Path(r"f:\PROJEKTY\vinted\vinted\testy_camoufox\vinted.har")
OUT_DIR = Path(r"f:\PROJEKTY\vinted\vinted\testy_camoufox")

print(f"[LOAD] {HAR}")
data = json.loads(HAR.read_text(encoding="utf-8", errors="replace"))
entries = data.get("log", {}).get("entries", [])
print(f"[LOAD] {len(entries)} entries")

# =============================================================================
# 1. Pełna inspekcja 12 entries icg-in (4 sekwencje)
# =============================================================================
print("\n" + "=" * 80)
print("[1] INCOGNIA AUTH - PEŁNA INSPEKCJA")
print("=" * 80)

icg_indices = [100, 101, 103, 258, 259, 261, 487, 488, 490, 641, 642, 643]

for idx in icg_indices:
    e = entries[idx]
    req = e.get("request", {})
    resp = e.get("response", {})
    print(f"\n{'='*60}")
    print(f"ENTRY {idx}: {req.get('method')} {req.get('url')[:100]}")
    print(f"{'='*60}")

    # Request headers
    print(f"  REQUEST HEADERS ({len(req.get('headers', []))}):")
    for h in req.get("headers", []):
        name = h.get("name", "")
        val = h.get("value", "")
        if name.lower() in ["cookie", "set-cookie", "authorization", "x-incognia", "x-api-key"]:
            print(f"    {name}: {val[:200]}")
        elif name.lower() not in ["accept", "accept-language", "user-agent", "origin", "referer"]:
            print(f"    {name}: {val[:120]}")

    # Request body
    req_body = req.get("postData", {})
    if req_body:
        text = req_body.get("text", "")
        print(f"\n  REQUEST BODY ({len(text)} B, mime={req_body.get('mimeType')}):")
        print(f"    {text[:500]}")

    # Response headers
    print(f"\n  RESPONSE HEADERS ({len(resp.get('headers', []))}):")
    for h in resp.get("headers", []):
        name = h.get("name", "")
        val = h.get("value", "")
        if name.lower() in ["set-cookie", "location", "x-incognia", "www-authenticate"]:
            print(f"    {name}: {val[:200]}")
        elif name.lower() not in ["content-length", "date", "server", "connection", "alt-svc", "vary"]:
            print(f"    {name}: {val[:120]}")

    # Response body (text + encoding + size + _transferSize)
    cont = resp.get("content", {})
    print(f"\n  RESPONSE BODY:")
    print(f"    size={cont.get('size')} _transferSize={cont.get('_transferSize')}")
    print(f"    mimeType={cont.get('mimeType')}")
    print(f"    compression={cont.get('compression')} encoding={cont.get('encoding')}")
    text = cont.get("text", "")
    if text:
        print(f"    TEXT ({len(text)} B): {text[:500]}")
    else:
        print(f"    NO TEXT CONTENT")

    # Query string
    qs = req.get("queryString", [])
    if qs:
        print(f"\n  QUERY STRING:")
        for q in qs:
            print(f"    {q.get('name')}: {q.get('value')[:200]}")
