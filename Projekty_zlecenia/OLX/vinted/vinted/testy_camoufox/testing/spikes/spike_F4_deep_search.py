# coding: utf-8
"""Spike F4: Głębokie przeszukanie WSZYSTKICH 53 plików JS pod Incognia/axios."""
import json
import re
import hashlib
from collections import defaultdict
from pathlib import Path

SCRIPTS_V1 = Path(r"C:\Temp\vinted_scripts")
SCRIPTS_V2 = Path(r"C:\Temp\vinted_scripts_v2")
OUTPUT = Path(r"C:\Temp\wynik_spike_F4_deep_search.json")

# Wzorce - bardziej szczegółowe niż B3
PATTERNS = {
    "incognia_keyword": re.compile(r"(?i)(incognia|incog\.com|pulseinsights|signals[_-]?sdk)"),
    "incognia_uuid": re.compile(r"0e806f9a[-]?[0-9a-f]{4}[-]?[0-9a-f]{4}[-]?[0-9a-f]{4}[-]?[0-9a-f]{12}"),
    "jwe_long": re.compile(r"eyJ[A-Za-z0-9_\-]{300,}"),
    "interceptor_axios": re.compile(r"interceptors?\.(?:request|response)\.use"),
    "axios_import": re.compile(r"axios(?:\.create|\.defaults|\.interceptors)"),
    "fetch_wrapper": re.compile(r"function\s*\w+\s*\([^)]*\)\s*\{[^}]*fetch\s*\("),
    "csrf_token": re.compile(r"(?i)x-csrf-token|csrf[_-]?token|csrfToken"),
    "checkout_build": re.compile(r"(?:checkout/build|purchases/build|purchase_items)"),
    "transaction_id": re.compile(r"(?:transaction[_-]?id|transactionId)"),
    "transaction_init": re.compile(r"(?:transactions/initiate|transactions/init|/transactions/\d+)"),
    "datadome_payload": re.compile(r"(?:dd_payload|datadomePayload|ddjskey)"),
    "incognia_token_var": re.compile(r"(?i)incognia(?:Token|Request|Token|Setup|Config|Sdk)"),
    "sdk_loader": re.compile(r"(?i)(?:sdkLoader|sdkUrl|sdk_url|loadScript|loadSdk)"),
    "dd_options": re.compile(r"(?:dataDomeOptions|ddoptions|ddjskey)"),
    "fingerprint_keys": re.compile(r"(?:fingerprint|webgl[_-]?hash|canvas[_-]?hash|audio[_-]?hash)"),
    "navigator_keys": re.compile(r"navigator\.(userAgent|platform|language|hardwareConcurrency|deviceMemory)"),
    "uat": re.compile(r"(?i)user.?agent"),
}

# Wyciąganie URL-i endpointów
API_URL_RE = re.compile(r'(?P<url>/api/v\d+/[A-Za-z0-9_\-/{}/.]+)')


def safe_match(text: str, m: re.Match, before: int = 100, after: int = 100) -> str:
    s = max(0, m.start() - before)
    e = min(len(text), m.end() + after)
    snippet = text[s:e].replace("\n", " ")
    return f"@{m.start()}: ...{snippet}..."


def analyze_file(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return {"filename": path.name, "error": repr(e)}

    info = {
        "filename": path.name,
        "size": len(text),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "matches": {},
        "api_endpoints": [],
    }

    for label, pat in PATTERNS.items():
        hits = []
        for m in pat.finditer(text):
            hits.append({
                "offset": m.start(),
                "match": m.group(0)[:100],
                "context": safe_match(text, m, 70, 70),
            })
            if len(hits) >= 8:  # max 8 per pattern per file
                break
        if hits:
            info["matches"][label] = hits

    # Wyciągnij wszystkie URL-e API
    api_urls = []
    seen = set()
    for m in API_URL_RE.finditer(text):
        u = m.group("url")
        if u not in seen:
            seen.add(u)
            api_urls.append(u)
    if api_urls:
        info["api_endpoints"] = api_urls[:30]

    return info


def main():
    files = sorted(list(SCRIPTS_V1.glob("*.js")) + list(SCRIPTS_V2.glob("*.js")))
    print(f"[F4] Analizuję {len(files)} plików...", flush=True)
    results = []
    summary = {"total_files": len(files), "pattern_hits": {label: 0 for label in PATTERNS}}

    for f in files:
        info = analyze_file(f)
        results.append(info)
        for label, hits in info.get("matches", {}).items():
            summary["pattern_hits"][label] += len(hits)

    OUTPUT.write_text(json.dumps({"summary": summary, "files": results}, ensure_ascii=False, indent=2),
                      encoding="utf-8")

    print(f"\n[F4] Zapisano {OUTPUT}", flush=True)
    print("\n[F4] Pattern hits:", flush=True)
    for label, n in summary["pattern_hits"].items():
        if n > 0:
            print(f"  {label}: {n}", flush=True)

    # Top pliki z matchami
    files_with_hits = [(f["filename"], sum(len(h) for h in f.get("matches", {}).values()))
                       for f in results]
    files_with_hits.sort(key=lambda x: -x[1])
    print("\n[F4] Top 10 plików z matchami:", flush=True)
    for fname, n in files_with_hits[:10]:
        print(f"  {n:5d}  {fname}", flush=True)

    # Specjalny output dla kluczowych wzorców
    print("\n\n=== INCOGNIA ===")
    for f in results:
        for label in ("incognia_keyword", "incognia_uuid", "incognia_token_var"):
            if label in f.get("matches", {}):
                for hit in f["matches"][label][:3]:
                    print(f"  [{label}] {f['filename']}: {hit['context'][:300]}")

    print("\n=== INTERCEPTOR/AXIOS ===")
    for f in results:
        for label in ("interceptor_axios", "axios_import"):
            if label in f.get("matches", {}):
                for hit in f["matches"][label][:2]:
                    print(f"  [{label}] {f['filename']}: {hit['context'][:250]}")

    print("\n=== CHECKOUT/TRANSACTION ===")
    for f in results:
        for label in ("checkout_build", "transaction_id", "transaction_init"):
            if label in f.get("matches", {}):
                for hit in f["matches"][label][:2]:
                    print(f"  [{label}] {f['filename']}: {hit['context'][:250]}")

    print("\n=== API ENDPOINTS (top 5 plików) ===")
    for f in results:
        if f.get("api_endpoints"):
            print(f"  {f['filename']}: {f['api_endpoints'][:10]}")
            if len([x for x in results if x.get('api_endpoints')]) >= 5:
                break


if __name__ == "__main__":
    main()
