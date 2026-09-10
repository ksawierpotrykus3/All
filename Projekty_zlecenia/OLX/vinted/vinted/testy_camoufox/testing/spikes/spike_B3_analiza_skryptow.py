# coding: utf-8
"""Spike B3: Statyczna analiza skryptów JS Vinted pod kątem Incognia/DataDome/JWE.

Pliki zminifikowane (1-2 długie linie), więc zwykły grep przeskakuje konteksty.
Podejście:
  - dla każdego pliku wyciągnij listę wszystkich matchów (z offsetem w bajtach)
  - wyciągnij krótki kontekst (80 znaków przed + match + 80 po)
  - zlicz unikalne stringi przy każdym matchu
  - wykryj URL-e, klucze API, nazwy funkcji
"""
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

SCRIPTS_DIR = Path(r"C:\Temp\vinted_scripts")
OUTPUT = Path(r"C:\Temp\wynik_spike_B3_analiza.json")

# Wzorce - grupowane tematycznie
PATTERNS = {
    "incognia_explicit": re.compile(r"(?i)incognia"),
    "jwe_token": re.compile(r"(?i)(x-incognia-request-token|jwe|jsonwebtoken|incognia_token)"),
    "datadome_keyword": re.compile(r"(?i)datadome"),
    "captcha_keyword": re.compile(r"(?i)captcha"),
    "fingerprint_keyword": re.compile(r"(?i)fingerprint"),
    "webgl_canvas": re.compile(r"(?i)(webgl|canvas\.|canvas2d|webgl2)"),
    "purchases_endpoint": re.compile(r"(purchases/checkout|/checkout/build|checkout_build)"),
    "sensor_sdk": re.compile(r"(?i)(sensor\.js|fpjs|signals-sdk|incognia-sdk)"),
    "post_call": re.compile(r"(?i)(XMLHttpRequest|fetch\(|navigator\.sendBeacon)"),
    "trust_token": re.compile(r"(?i)(trust[_-]?token|capkey|interception)"),
}

# Wyciąganie URL-i
URL_RE = re.compile(r'https?://[^\s\'"\\]{5,200}')
# Wyciąganie stringów krótszych (potencjalne klucze / endpointy)
STRING_RE = re.compile(r'[\'"`]([A-Za-z0-9_\-/.:?&=#%]{4,120})[\'"`]')
# Funkcje/zmienne (podejrzane nazwy z minified JS)
IDENT_RE = re.compile(r'\b([a-z][a-zA-Z0-9_]{2,40})\b')

# Stopwords
STOPWORDS = {
    "function", "return", "true", "false", "null", "undefined", "window", "document",
    "this", "that", "value", "length", "name", "type", "data", "error", "object",
    "string", "number", "boolean", "array", "promise", "callback", "result",
    "var", "let", "const", "new", "class", "extends", "import", "from", "export",
    "default", "async", "await", "yield", "of", "in", "for", "while", "if", "else",
    "try", "catch", "throw", "finally", "switch", "case", "break", "continue",
    "do", "typeof", "instanceof", "delete", "void", "with", "debugger", "static",
    "get", "set", "constructor", "prototype", "hasOwnProperty", "toString",
    "valueOf", "then", "catch", "finally", "resolve", "reject",
}


def truncate_context(text: str, m: re.Match, before: int = 60, after: int = 60) -> str:
    s = max(0, m.start() - before)
    e = min(len(text), m.end() + after)
    snippet = text[s:e].replace("\n", " ")
    return f"@{m.start()}: ...{snippet}..."


def analyze_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="ignore")
    info = {
        "filename": path.name,
        "size": len(text),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "matches": {},
        "urls": [],
        "top_strings": [],
        "suspicious_idents": [],
    }

    # 1) Patterny tematyczne
    for label, pat in PATTERNS.items():
        hits = []
        for m in pat.finditer(text):
            hits.append({
                "offset": m.start(),
                "match": m.group(0),
                "context": truncate_context(text, m, 50, 50),
            })
            if len(hits) >= 5:  # max 5 per pattern per file
                break
        if hits:
            info["matches"][label] = hits

    # 2) URL-e (max 30)
    urls = []
    seen = set()
    for m in URL_RE.finditer(text):
        u = m.group(0).rstrip("'\"`;),]}\\")
        if u and u not in seen:
            seen.add(u)
            urls.append(u)
        if len(urls) >= 30:
            break
    info["urls"] = urls

    # 3) Top strings (nie-fingerprint count)
    string_counter = Counter()
    for m in STRING_RE.finditer(text):
        s = m.group(1)
        if len(s) < 8 or len(s) > 100:
            continue
        if s.startswith(("http://", "https://", "/")):
            continue
        if s in STOPWORDS or s.lower() in STOPWORDS:
            continue
        # Preferuj stringi, które wyglądają jak API endpoint, klucz, nagłówek
        if any(c in s for c in "/:._-") or "incognia" in s.lower() or "datadome" in s.lower():
            string_counter[s] += 1
    info["top_strings"] = string_counter.most_common(20)

    # 4) Identyfikatory minified (top 20 najczęstszych > 4 znaków)
    ident_counter = Counter()
    for m in IDENT_RE.finditer(text):
        ident = m.group(1)
        if ident in STOPWORDS or ident.lower() in STOPWORDS:
            continue
        if len(ident) < 4:
            continue
        ident_counter[ident] += 1
    info["suspicious_idents"] = ident_counter.most_common(20)

    return info


def main():
    files = sorted(SCRIPTS_DIR.glob("*.js"))
    print(f"[B3] Analizuję {len(files)} plików...", flush=True)
    results = []
    summary = {"total_files": len(files)}
    file_counters = {label: 0 for label in PATTERNS}
    for f in files:
        info = analyze_file(f)
        results.append(info)
        for label in PATTERNS:
            if label in info["matches"]:
                file_counters[label] += 1
    for label, cnt in file_counters.items():
        summary[f"files_with_{label}"] = cnt

    OUTPUT.write_text(json.dumps({
        "summary": summary,
        "files": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n[B3] Zapisano {OUTPUT}", flush=True)
    print(json.dumps(summary, indent=2, ensure_ascii=False), flush=True)

    # Wypisz kluczowe URL-e i matche
    print("\n[B3] Pliki zawierające 'datadome':", flush=True)
    for r in results:
        if "datadome_keyword" in r["matches"]:
            print(f"  {r['filename']}  ({len(r['matches']['datadome_keyword'])} matchów)", flush=True)
            for hit in r["matches"]["datadome_keyword"][:3]:
                print(f"    -> {hit['context'][:200]}", flush=True)
    print("\n[B3] Pliki zawierające 'incognia':", flush=True)
    for r in results:
        if "incognia_explicit" in r["matches"]:
            print(f"  {r['filename']}", flush=True)
            for hit in r["matches"]["incognia_explicit"][:3]:
                print(f"    -> {hit['context'][:200]}", flush=True)
    print("\n[B3] Pliki z 'purchases/checkout':", flush=True)
    for r in results:
        if "purchases_endpoint" in r["matches"]:
            print(f"  {r['filename']}", flush=True)
            for hit in r["matches"]["purchases_endpoint"][:3]:
                print(f"    -> {hit['context'][:200]}", flush=True)
    print("\n[B3] Pliki z 'sensor/sdk':", flush=True)
    for r in results:
        if "sensor_sdk" in r["matches"]:
            print(f"  {r['filename']}", flush=True)


if __name__ == "__main__":
    main()
