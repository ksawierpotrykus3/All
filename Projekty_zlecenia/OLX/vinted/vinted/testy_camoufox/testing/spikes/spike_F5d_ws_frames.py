"""F5d: Szczegółowa analiza WebSocket frames + klucz RSA + inline scripts z HAR.

Wyciąga:
  1. Wszystkie WebSocket messages z HAR (text/binary)
  2. Sprawdza response bodies pod kątem BEGIN PUBLIC KEY / RSA-OAEP
  3. Szuka inline scripts z JWE / publicKey / RSA
  4. Pokazuje wszystkie entry zawierające 'incognia' lub 'icg-in'
"""
from __future__ import annotations

import json
import re
import base64
from pathlib import Path

HAR = Path(r"f:\PROJEKTY\vinted\vinted\testy_camoufox\vinted.har")
OUT_DIR = Path(r"C:\Temp")
OUT_DIR.mkdir(parents=True, exist_ok=True)

print(f"[LOAD] {HAR} ({HAR.stat().st_size:,} bytes)")
data = json.loads(HAR.read_text(encoding="utf-8", errors="replace"))
log = data.get("log", {})
entries = log.get("entries", [])
print(f"[LOAD] {len(entries)} entries")

# =============================================================================
# 1. WebSocket messages - szukamy _webSocketMessages
# =============================================================================
print("\n" + "=" * 80)
print("[1] WEBSOCKET MESSAGES")
print("=" * 80)

ws_total = 0
ws_urls = {}
ws_msg_examples = []

for idx, e in enumerate(entries):
    msgs = e.get("_webSocketMessages") or []
    if msgs:
        url = e.get("request", {}).get("url", "?")
        ws_urls.setdefault(url, []).append((idx, len(msgs)))
        ws_total += len(msgs)
        if len(ws_msg_examples) < 4:
            for m in msgs[:3]:
                ws_msg_examples.append({
                    "entry_idx": idx,
                    "url": url,
                    "type": m.get("type"),
                    "opcode": m.get("opcode"),
                    "time": m.get("time"),
                    "data_preview": (m.get("data") or "")[:500],
                    "data_length": len(m.get("data") or ""),
                })

print(f"WebSocket entries: {len(ws_urls)} URLs, {ws_total} total messages")
for url, items in ws_urls.items():
    print(f"  {url}")
    for idx, cnt in items[:5]:
        print(f"    entry {idx}: {cnt} msgs")
    if len(items) > 5:
        print(f"    ... and {len(items)-5} more")

print(f"\nWebSocket message previews (first 4):")
for ex in ws_msg_examples:
    print(f"\n  --- entry {ex['entry_idx']} ({ex['type']}/{ex['opcode']}) ---")
    print(f"  URL: {ex['url']}")
    print(f"  Length: {ex['data_length']}")
    print(f"  Preview: {ex['data_preview'][:400]}")

# =============================================================================
# 2. Szukamy klucza publicznego RSA w response bodies
# =============================================================================
print("\n" + "=" * 80)
print("[2] KLUCZ PUBLICZNY RSA W RESPONSE BODIES")
print("=" * 80)

rsa_patterns = [
    re.compile(r"-----BEGIN PUBLIC KEY-----", re.I),
    re.compile(r"-----BEGIN RSA PUBLIC KEY-----", re.I),
    re.compile(r"-----BEGIN PUBLIC KEY-----\s*([A-Za-z0-9+/=\s]+?)\s*-----END PUBLIC KEY-----", re.I | re.S),
    re.compile(r'"publicKey"\s*:\s*"([^"]+)"'),
    re.compile(r'"public_key"\s*:\s*"([^"]+)"'),
    re.compile(r'"jwk"\s*:\s*\{'),
    re.compile(r'RSA-OAEP', re.I),
    re.compile(r'RSASSA-PKCS1-v1_5', re.I),
    re.compile(r'"alg"\s*:\s*"(RSA|RSA-OAEP)"'),
]

rsa_hits = []
for idx, e in enumerate(entries):
    body = e.get("response", {}).get("content", {}).get("text", "")
    if not body:
        continue
    for pat in rsa_patterns:
        m = pat.search(body)
        if m:
            rsa_hits.append({
                "entry_idx": idx,
                "url": e.get("request", {}).get("url", "?"),
                "pattern": pat.pattern[:40],
                "match_preview": m.group(0)[:200],
                "body_size": len(body),
            })
            break

print(f"RSA hits: {len(rsa_hits)}")
for h in rsa_hits[:20]:
    print(f"\n  entry {h['entry_idx']} ({h['body_size']} B):")
    print(f"    URL: {h['url'][:120]}")
    print(f"    Match ({h['pattern']}): {h['match_preview'][:200]}")

# =============================================================================
# 3. Szukamy inline scripts z JWE / RSA w HTML
# =============================================================================
print("\n" + "=" * 80)
print("[3] INLINE SCRIPTS Z JWE / RSA W HTML")
print("=" * 80)

html_patterns = [
    re.compile(r"Incognia", re.I),
    re.compile(r"INCOGNIA_WEB_CLIENT_SIDE_KEY"),
    re.compile(r"0e806f9a-66d6-4c7e-bd94-382236e16bc8"),
    re.compile(r"incognia", re.I),
    re.compile(r"icg-in", re.I),
    re.compile(r"conn-check", re.I),
    re.compile(r"x-incognia-request-token", re.I),
    re.compile(r"window\.Incognia"),
    re.compile(r"IncogniaClient"),
    re.compile(r"signals-sdk"),
    re.compile(r"jwe", re.I),
    re.compile(r"RSA-OAEP", re.I),
    re.compile(r"publicKey", re.I),
]

inline_hits = []
for idx, e in enumerate(entries):
    body = e.get("response", {}).get("content", {}).get("text", "")
    if not body or "<html" not in body[:500].lower():
        continue
    for pat in html_patterns:
        m = pat.search(body)
        if m:
            ctx_start = max(0, m.start() - 100)
            ctx_end = min(len(body), m.end() + 200)
            inline_hits.append({
                "entry_idx": idx,
                "url": e.get("request", {}).get("url", "?")[:120],
                "pattern": pat.pattern,
                "context": body[ctx_start:ctx_end],
            })
            break

print(f"Inline HTML hits: {len(inline_hits)}")
seen = set()
for h in inline_hits[:20]:
    key = (h["url"], h["pattern"])
    if key in seen:
        continue
    seen.add(key)
    print(f"\n  entry {h['entry_idx']}: {h['url']}")
    print(f"    Match: {h['pattern']}")
    print(f"    Context: {h['context'][:300]}")

# =============================================================================
# 4. Wszystkie entries zawierające 'incognia' lub 'icg-in'
# =============================================================================
print("\n" + "=" * 80)
print("[4] ENTRIES Z 'incognia' LUB 'icg-in'")
print("=" * 80)

inc_entries = []
for idx, e in enumerate(entries):
    url = e.get("request", {}).get("url", "")
    if "incognia" in url.lower() or "icg-in" in url.lower():
        req_h = e.get("request", {}).get("headers", [])
        resp_h = e.get("response", {}).get("headers", [])
        inc_entries.append({
            "idx": idx,
            "url": url,
            "method": e.get("request", {}).get("method"),
            "status": e.get("response", {}).get("status"),
            "req_h_count": len(req_h),
            "resp_h_count": len(resp_h),
        })

print(f"Entries: {len(inc_entries)}")
for ie in inc_entries[:30]:
    print(f"  entry {ie['idx']}: {ie['method']} {ie['url'][:120]} -> {ie['status']}")

# =============================================================================
# 5. Zapisz wyniki
# =============================================================================
out = {
    "ws_urls": {u: [{"idx": i, "msg_count": c} for i, c in items] for u, items in ws_urls.items()},
    "ws_msg_examples": ws_msg_examples,
    "rsa_hits": rsa_hits,
    "inline_html_hits": inline_hits,
    "inc_entries": inc_entries,
    "ws_total_messages": ws_total,
}

out_path = OUT_DIR / "wynik_spike_F5d_ws_frames.json"
out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n[SAVE] {out_path}")
