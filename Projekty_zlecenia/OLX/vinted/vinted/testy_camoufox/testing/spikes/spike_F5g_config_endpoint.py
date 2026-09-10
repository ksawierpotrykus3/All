"""F5g: Sprawdź zawartość odpowiedzi z api.vinted.pl/j3r4zw/v1/config (entry 32 w HAR)
   oraz z api.vinted.pl/j3r4zw/v1/consume (entries 88, 348, 524, 679).

To są kandydaci na:
  - Klucz publiczny RSA Incognia
  - URL consume (gdzie wysyłane są zaszyfrowane dane)
"""
import json
import base64
from pathlib import Path

HAR = Path(r"f:\PROJEKTY\vinted\vinted\testy_camoufox\vinted.har")
OUT = Path(r"f:\PROJEKTY\vinted\vinted\testy_camoufox\wynik_spike_F5g_config.json")

data = json.loads(HAR.read_text(encoding="utf-8", errors="replace"))
entries = data["log"]["entries"]

# Szukamy WSZYSTKICH requestów do api.vinted.pl
print("=" * 80)
print("REQUESTY DO api.vinted.pl (Vinted API)")
print("=" * 80)

vinted_api_requests = []
for idx, e in enumerate(entries):
    url = e.get("request", {}).get("url", "")
    if "api.vinted.pl" in url or "vinted.pl/api" in url:
        method = e.get("request", {}).get("method", "?")
        status = e.get("response", {}).get("status", 0)
        size = e.get("response", {}).get("content", {}).get("size", 0)
        body = e.get("response", {}).get("content", {}).get("text", "")
        vinted_api_requests.append({
            "idx": idx,
            "method": method,
            "url": url,
            "status": status,
            "size": size,
            "body": body,
        })
        print(f"  entry {idx}: [{status}] {method} {url[:80]} ({size} B)")

# Zapisz wszystkie body do pliku
out = {"vinted_api": vinted_api_requests}
OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n[SAVE] {OUT} ({OUT.stat().st_size:,} B)")

# Sprawdź czy jest jakiś response z "BEGIN PUBLIC KEY" lub base64 RSA key
print("\n" + "=" * 80)
print("SZUKAM KLUCZA RSA / CONFIG W BODY")
print("=" * 80)
import re

for req in vinted_api_requests:
    body = req["body"]
    if not body:
        continue
    # Szukaj base64 RSA
    b64_long = re.findall(r'([A-Za-z0-9+/]{50,}={0,2})', body)
    if b64_long:
        print(f"\n  entry {req['idx']}: {req['url'][:80]}")
        print(f"    size={req['size']}")
        print(f"    body={body[:500]}")
        for b in b64_long[:3]:
            try:
                decoded = base64.b64decode(b + "=" * ((4 - len(b) % 4) % 4))
                print(f"    base64 ({len(b)} chars) -> {len(decoded)} bytes, first 30: {decoded[:30]}")
                # Sprawdź czy to ASN.1 RSA public key
                if decoded.startswith(b'\x30'):
                    print(f"    [!!!] To wygląda na ASN.1 DER (RSA public key)")
            except Exception as e:
                print(f"    base64 ({len(b)} chars) -> decode error: {e}")
