"""F5f2: Znajdź źródło klucza publicznego RSA dla JWE Incognia w HAR.

Sprawdzamy:
1. Wszystkie hosty w HAR (może jest osobna subdomena Incognia)
2. Wszystkie requesty PRZED pierwszym /connectioncheck (entry 100)
3. Wszystkie HTML responses Vinted (szukamy base64 RSA)
4. Wszystkie małe pliki JS (< 50KB) ładowane PRZED entry 100 - szukamy RSA builder
"""
import json
import re
import base64
from pathlib import Path
from urllib.parse import urlparse

HAR = Path(r"f:\PROJEKTY\vinted\vinted\testy_camoufox\vinted.har")
OUT = Path(r"f:\PROJEKTY\vinted\vinted\testy_camoufox\wynik_spike_F5f2_klucz_rsa.json")

data = json.loads(HAR.read_text(encoding="utf-8", errors="replace"))
entries = data["log"]["entries"]

# === 1. Wszystkie hosty ===
print("=" * 80)
print("[1] HOSTY W HAR")
print("=" * 80)
hosts = {}
for e in entries:
    url = e.get("request", {}).get("url", "")
    h = urlparse(url).netloc
    hosts[h] = hosts.get(h, 0) + 1
for h, c in sorted(hosts.items(), key=lambda x: -x[1]):
    print(f"  {h}: {c}")

# === 2. Wszystkie requesty PRZED entry 100 (pierwszy /connectioncheck) ===
print("\n" + "=" * 80)
print("[2] REQUESTY PRZED ENTRY 100 (kontekst ładowania strony)")
print("=" * 80)
pre = entries[:100]
print(f"Liczba entries przed pierwszym /connectioncheck: {len(pre)}")
for e in pre:
    url = e.get("request", {}).get("url", "")
    status = e.get("response", {}).get("status", 0)
    size = e.get("response", {}).get("content", {}).get("size", 0)
    print(f"  [{status}] {e.get('request', {}).get('method', '?')} {url[:80]} ({size} B)")

# === 3. HTML responses Vinted - szukamy klucza RSA ===
print("\n" + "=" * 80)
print("[3] HTML RESPONSES Z KLUCZEM RSA")
print("=" * 80)
rsa_b64_pattern = re.compile(r'([A-Za-z0-9+/]{50,}={0,2})')
rsa_patterns = [
    re.compile(r'(MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8[A-Za-z0-9+/=]{100,})'),
    re.compile(r'(MIIBCgKCAQ[A-Za-z0-9+/=]{100,})'),
    re.compile(r'BEGIN PUBLIC KEY', re.I),
    re.compile(r'RSA-OAEP', re.I),
]

html_hits = []
for idx, e in enumerate(entries):
    body = e.get("response", {}).get("content", {}).get("text", "")
    if not body or "<html" not in body[:500].lower() and "vinted" not in body[:1000]:
        continue
    for pat in rsa_patterns:
        m = pat.search(body)
        if m:
            html_hits.append({
                "idx": idx,
                "url": e.get("request", {}).get("url", "")[:80],
                "pattern": pat.pattern[:40],
                "match": m.group(0)[:200],
            })

print(f"HTML RSA hits: {len(html_hits)}")
for h in html_hits[:5]:
    print(f"  entry {h['idx']}: {h['url']}")
    print(f"    match: {h['match'][:100]}")

# === 4. Pliki JS ładowane PRZED entry 100 ===
print("\n" + "=" * 80)
print("[4] PLIKI JS PRZED ENTRY 100 (szukamy RSA builder)")
print("=" * 80)
js_pre = []
for idx, e in enumerate(pre):
    url = e.get("request", {}).get("url", "")
    if url.endswith(".js") or "javascript" in e.get("response", {}).get("content", {}).get("mimeType", ""):
        size = e.get("response", {}).get("content", {}).get("size", 0)
        body = e.get("response", {}).get("content", {}).get("text", "")[:200]
        js_pre.append({"idx": idx, "url": url[:100], "size": size, "preview": body[:100]})

print(f"JS przed entry 100: {len(js_pre)}")
for j in js_pre[:20]:
    print(f"  entry {j['idx']}: {j['size']} B {j['url']}")

# === 5. Pliki JS > 50KB (gdzie może być builder JWE) ===
print("\n" + "=" * 80)
print("[5] NAJWIĘKSZE PLIKI JS - szukamy RSA / JWE")
print("=" * 80)
js_files = []
for idx, e in enumerate(entries):
    url = e.get("request", {}).get("url", "")
    cont = e.get("response", {}).get("content", {})
    size = cont.get("size", 0)
    mime = cont.get("mimeType", "")
    if url.endswith(".js") and size > 30000:
        body = cont.get("text", "")
        # Szukamy specyficznych wzorców
        signals = []
        if "RSA-OAEP" in body or "RsaOaep" in body or "RSA_OAEP" in body:
            signals.append("RSA-OAEP")
        if "jwe" in body.lower():
            signals.append("jwe")
        if "publicKey" in body or "public_key" in body:
            signals.append("publicKey")
        if "BEGIN PUBLIC KEY" in body:
            signals.append("BEGIN PUBLIC KEY")
        if "forger" in body.lower() or "node-forge" in body.lower() or "jsrsasign" in body.lower():
            signals.append("forge/jsrsasign")
        if "incognia" in body.lower() or "icg-in" in body.lower():
            signals.append("incognia")
        if "k7v3q2" in url or "ateam" in url:
            signals.append("ATEAM")
        js_files.append({
            "idx": idx,
            "url": url[:120],
            "size": size,
            "signals": signals,
        })

print(f"JS files > 30KB: {len(js_files)}")
for j in sorted(js_files, key=lambda x: -x["size"])[:15]:
    print(f"  entry {j['idx']}: {j['size']:,} B {j['url']}")
    if j["signals"]:
        print(f"    SIGNALS: {j['signals']}")

# === 6. ZAPISZ WYNIKI ===
out = {
    "hosts": hosts,
    "pre_first_conncheck_count": len(pre),
    "js_pre_count": len(js_pre),
    "html_rsa_hits": html_hits,
    "big_js_files": js_files,
}
OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n[SAVE] {OUT}")
