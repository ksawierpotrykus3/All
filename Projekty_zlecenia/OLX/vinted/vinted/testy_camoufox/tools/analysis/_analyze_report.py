"""Analiza raportu spike F1 real Firefox."""
import json
import sys
from collections import Counter

P = r"C:\Temp\wynik_spike_F1_real_firefox.json"
d = json.load(open(P, encoding="utf-8"))

print("=" * 80)
print("CONSOLE ERRORS (deduplikowane):")
print("=" * 80)
seen = set()
for e in d["console_errors"]:
    key = e["text"][:120]
    if key in seen:
        continue
    seen.add(key)
    print(f"[{e['type']}] {e['text'][:300]}")
print(f"\nUnikalne console errors: {len(seen)} / {len(d['console_errors'])}")

print()
print("=" * 80)
print("ODPOWIEDZI Z 4xx/5xx:")
print("=" * 80)
errs = [r for r in d["responses"] if r["status"] >= 400]
print(f"Razem: {len(errs)}")
status_counter = Counter(r["status"] for r in errs)
print(f"Wg statusu: {dict(status_counter)}")
for r in errs[:30]:
    print(f"  {r['status']} {r['url'][:200]}")

print()
print("=" * 80)
print("ODPOWIEDZI CHECKOUT / PURCHASE:")
print("=" * 80)
checks = [r for r in d["responses"] if "checkout" in r["url"].lower() or "purchase" in r["url"].lower()]
print(f"Razem: {len(checks)}")
for r in checks[:30]:
    print(f"  {r['status']} {r['url'][:200]}")

print()
print("=" * 80)
print("REQUESTY checkout / purchase (POST):")
print("=" * 80)
posts = [r for r in d["all_requests"] if r["rtype"] in ("xhr", "fetch")
         and ("checkout" in r["url"].lower() or "purchase" in r["url"].lower())
         and r["method"] == "POST"]
print(f"Razem: {len(posts)}")
for r in posts[:20]:
    print(f"  {r['method']} {r['url'][:200]}  post={r['post'][:120] if r['post'] else None}")

print()
print("=" * 80)
print("DANE / COOKIES PO IMPORCIE:")
print("=" * 80)
print(f"Zaimportowane cookies: {d['imported_cookies_count']}")
print(f"User zalogowany: {d['summary']['login_status']} (id={d['summary']['user_id']})")

print()
print("=" * 80)
print("TYPY ZASOBOW (rtypes):")
print("=" * 80)
rtypes = Counter(r["rtype"] for r in d["all_requests"])
for k, v in rtypes.most_common():
    print(f"  {k}: {v}")

print()
print("=" * 80)
print("UNIKALNE HOSTY:")
print("=" * 80)
from urllib.parse import urlparse
hosts = Counter(urlparse(r["url"]).netloc for r in d["all_requests"])
for h, c in hosts.most_common():
    print(f"  {c:4d}  {h}")
