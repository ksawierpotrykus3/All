"""F5f: Szuka klucza publicznego RSA / fingerprint payload w WSZYSTKICH response bodies HAR.
"""
import json
import re
import base64
from pathlib import Path

HAR = Path(r"f:\PROJEKTY\vinted\vinted\testy_camoufox\vinted.har")
OUT = Path(r"f:\PROJEKTY\vinted\vinted\testy_camoufox\wynik_spike_F5f_inline_search.json")

data = json.loads(HAR.read_text(encoding="utf-8", errors="replace"))
entries = data["log"]["entries"]

# Pełniejsze wzorce
patterns = {
    "BEGIN PUBLIC KEY": re.compile(r"-----BEGIN PUBLIC KEY-----", re.I),
    "BEGIN RSA PUBLIC KEY": re.compile(r"-----BEGIN RSA PUBLIC KEY-----", re.I),
    "publicKey JSON": re.compile(r'"publicKey"\s*:\s*"([A-Za-z0-9+/=_\-\.]{20,})"', re.I),
    "publicKey JWK": re.compile(r'"publicKey"\s*:\s*\{', re.I),
    "BEGIN PRIVATE KEY": re.compile(r"-----BEGIN PRIVATE KEY-----", re.I),
    "RSA-OAEP": re.compile(r"RSA-OAEP", re.I),
    "JWE header alg enc": re.compile(r'\\?"alg\\?":\\?"(RSA[^"\\]*)\\?"[^}]*\\?"enc\\?":\\?"([^"\\]+)\\?"'),
    "jwe explicit": re.compile(r"\bjwe\b", re.I),
    "x5c cert chain": re.compile(r'\\?"x5c\\?"\s*:\s*\['),
    "Modulus Base64": re.compile(r'\\?"n\\?"\s*:\s*"([A-Za-z0-9+/=_\-]{20,})"'),
    "Exponent": re.compile(r'\\?"e\\?"\s*:\s*"([A-Za-z0-9+/=]+)"'),
    "atob btoa crypto": re.compile(r"\b(atob|btoa|crypto\.subtle|forge|pkjcs|jose)\b"),
    "RSA-OAEP encode": re.compile(r"RSA-OAEP[\"']?\s*[:,)]"),
    "Forge pkcs": re.compile(r"forge\.pkcs|forge\.rsa|node-forge|jsrsasign"),
}

results = {}
for pname, pat in patterns.items():
    results[pname] = []

# Dekoduj nagłówki JWE z request bodies /netconn connectioncheck
print("Dekodowanie nagłówków JWE z connectioncheck request bodies...")
jwe_tokens = []
for idx in [100, 258, 487, 641]:
    body = entries[idx]["request"].get("postData", {}).get("text", "")
    if body and body.startswith("eyJ"):
        try:
            header_b64 = body.split(".")[0]
            # padding
            header_b64 += "=" * ((4 - len(header_b64) % 4) % 4)
            header_json = base64.urlsafe_b64decode(header_b64).decode("utf-8", errors="replace")
            jwe_tokens.append({"idx": idx, "header": header_json, "parts": body.count(".")})
        except Exception as e:
            jwe_tokens.append({"idx": idx, "error": str(e), "parts": body.count(".")})

print(f"JWE tokens: {len(jwe_tokens)}")
for t in jwe_tokens:
    print(f"  entry {t['idx']}: parts={t.get('parts')} header={t.get('header')}")

# Szukaj wzorców we wszystkich response bodies
print(f"\nPrzeszukiwanie {len(entries)} response bodies...")
hits = []
for idx, e in enumerate(entries):
    body = e.get("response", {}).get("content", {}).get("text", "")
    if not body:
        continue
    for pname, pat in patterns.items():
        for m in pat.finditer(body):
            ctx_start = max(0, m.start() - 60)
            ctx_end = min(len(body), m.end() + 100)
            results[pname].append({
                "idx": idx,
                "url": e.get("request", {}).get("url", "")[:80],
                "match": m.group(0)[:150],
                "context": body[ctx_start:ctx_end],
            })

# Zapisz
out = {
    "jwe_tokens": jwe_tokens,
    "pattern_hits": results,
}
OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n[SAVE] {OUT}")

print("\n=== PODSUMOWANIE WZORCÓW ===")
for pname, lst in results.items():
    print(f"  {pname}: {len(lst)} hits")
    for h in lst[:3]:
        print(f"    entry {h['idx']}: {h['match'][:80]}")
        print(f"      ctx: {h['context'][:150]}")
