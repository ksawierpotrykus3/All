# coding: utf-8
"""Spike F5: Analiza vinted.har (48 MB) pod kątem Incognia + sekwencji API.

HAR zawiera pełny flow: od wejścia na stronę przedmiotu do momentu płatności.
To potencjalnie ujawni:
- kiedy SDK Incognia się ładuje (jeśli w ogóle)
- czy jest request do api.incognia.com / pulseinc.com
- skąd pochodzi x-incognia-request-token (który request go zwraca)
- pełną sekwencję POST /api/v2/purchases/checkout/build + /transactions/*
- czy są alternatywne endpointy (graphql, /v3) z tokenem Incognia
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

HAR_PATH = Path(r"f:\PROJEKTY\vinted\vinted\testy_camoufox\vinted.har")
OUTPUT = Path(r"C:\Temp\wynik_spike_F5_har_analysis.json")

# HAR to standardowy format: log.entries[]
# Każdy entry: request.url, request.headers, request.postData
#                   response.status, response.headers, response.content

INC_SDK_PATTERNS = [
    r"incognia",
    r"pulseinc",
    r"signals-sdk",
    r"incognia-sdk",
    r"x-incognia-request-token",
    r"IncogniaToken",
    r"incogniaToken",
    r"INCOGNIA_WEB_CLIENT_SIDE_KEY",
    r"0e806f9a-66d6-4c7e-bd94-382236e16bc8",
]

# Regex do wyciągania URL-i API
API_URL_RE = re.compile(r"^https?://(?:www\.vinted\.[a-z]+|api\.vinted\.[a-z]+|[a-z0-9]+\.vinted\.[a-z]+)/api/v\d+/([^\?]+)")
INC_HOST_RE = re.compile(r"^https?://([^/]*incognia[^/]*|[^/]*pulseinc[^/]*)", re.IGNORECASE)


def classify_url(url: str) -> tuple:
    """Zwraca (kategoria, szczegóły)."""
    m = API_URL_RE.match(url)
    if m:
        return ("vinted_api", m.group(1))
    if INC_HOST_RE.match(url):
        return ("incognia_cdn", url)
    if "datadome" in url.lower():
        return ("datadome", url[:120])
    if "vinted" in url.lower() and ".js" in url.lower():
        return ("vinted_js", url[:120])
    if "vinted" in url.lower():
        return ("vinted_other", url[:120])
    if ".js" in url.lower():
        return ("other_js", url[:120])
    return ("other", url[:120])


def extract_jwe(text: str) -> list:
    """Szukaj tokenów JWE (eyJ... 300+ znaków)."""
    return re.findall(r"eyJ[A-Za-z0-9_\-]{300,}", text)


def main():
    if not HAR_PATH.exists():
        print(f"BŁĄD: HAR nie istnieje: {HAR_PATH}", flush=True)
        return

    print(f"[F5] Wczytuję HAR: {HAR_PATH} ({HAR_PATH.stat().st_size // 1024 // 1024} MB)", flush=True)
    with HAR_PATH.open(encoding="utf-8") as f:
        har = json.load(f)

    entries = har.get("log", {}).get("entries", [])
    print(f"[F5] Wpisy w HAR: {len(entries)}", flush=True)

    # Statystyki URL-i
    by_category = defaultdict(list)
    method_counter = Counter()
    status_counter = Counter()
    incognia_requests = []
    jwe_tokens = []
    post_body_with_incognia = []
    headers_with_incognia = []

    # Specjalne: tylko POST do /api/v2
    vinted_api_posts = []
    cookies_set_during_session = []  # cookies ustawione przez Vinted

    for i, e in enumerate(entries):
        req = e.get("request", {})
        resp = e.get("response", {})
        url = req.get("url", "")
        method = req.get("method", "GET")
        status = resp.get("status", 0)
        method_counter[method] += 1
        status_counter[status] += 1

        cat, detail = classify_url(url)
        by_category[cat].append({
            "i": i, "url": url, "method": method, "status": status,
            "time": e.get("time", 0),
        })

        # Szukaj Incognia
        url_lower = url.lower()
        if any(re.search(pat, url_lower) for pat in INC_SDK_PATTERNS):
            incognia_requests.append({"i": i, "url": url, "method": method, "status": status})

        # Headers - szukaj x-incognia-request-token
        for h in req.get("headers", []):
            h_name = h.get("name", "").lower()
            h_value = h.get("value", "")
            if "incognia" in h_name or "incognia" in h_value.lower():
                if "incognia" in h_name:
                    headers_with_incognia.append({
                        "i": i, "url": url[:100], "header": h_name,
                        "value_preview": h_value[:80] + "..." if len(h_value) > 80 else h_value,
                        "value_len": len(h_value),
                    })

        # Body POST - szukaj Incognia
        if method in ("POST", "PUT", "PATCH"):
            post = req.get("postData", {})
            text = post.get("text", "") or ""
            if "incognia" in text.lower():
                post_body_with_incognia.append({
                    "i": i, "url": url[:120], "body_preview": text[:500],
                })

        # Response body - szukaj JWE tokenów (w content)
        content = resp.get("content", {})
        resp_text = content.get("text", "") or ""
        if "incognia" in resp_text.lower():
            tokens = extract_jwe(resp_text)
            for t in tokens:
                jwe_tokens.append({
                    "i": i, "url": url[:120], "status": status,
                    "jwe_preview": t[:100] + "...", "len": len(t),
                })

        # Zapamiętaj POST do vinted API
        if cat == "vinted_api" and method == "POST":
            post_data = req.get("postData", {}).get("text", "")[:1000]
            vinted_api_posts.append({
                "i": i, "url": url[:120], "status": status,
                "post_preview": post_data,
                "time": e.get("time", 0),
            })

        # Zapamiętaj cookies ustawiane przez response
        for h in resp.get("headers", []):
            if h.get("name", "").lower() == "set-cookie":
                cookies_set_during_session.append({
                    "i": i, "url": url[:100],
                    "cookie": h.get("value", "")[:200],
                })

    # Raport
    report = {
        "har_size_mb": round(HAR_PATH.stat().st_size / 1024 / 1024, 1),
        "total_entries": len(entries),
        "method_counter": dict(method_counter),
        "status_counter": dict(status_counter),
        "categories": {k: len(v) for k, v in by_category.items()},
        "incognia_cdn_requests": incognia_requests[:30],
        "incognia_cdn_count": len(incognia_requests),
        "jwe_tokens_found": jwe_tokens[:30],
        "jwe_tokens_count": len(jwe_tokens),
        "post_body_with_incognia": post_body_with_incognia[:30],
        "post_body_incognia_count": len(post_body_with_incognia),
        "headers_with_incognia": headers_with_incognia[:30],
        "headers_incognia_count": len(headers_with_incognia),
        "vinted_api_posts_count": len(vinted_api_posts),
        "vinted_api_posts": vinted_api_posts[:50],
        "cookies_set_count": len(cookies_set_during_session),
        "cookies_incognia_related": [c for c in cookies_set_during_session
                                       if "incognia" in c.get("cookie", "").lower()][:10],
    }

    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[F5] Zapisano {OUTPUT}", flush=True)

    print("\n=== KATEGORIE URL-i ===")
    for cat, count in sorted(report["categories"].items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")

    print("\n=== STATUS COUNTER (top 10) ===")
    for status, count in sorted(status_counter.items(), key=lambda x: -x[1])[:10]:
        print(f"  {status}: {count}")

    print("\n=== INCOGNIA CDN REQUESTS ===")
    print(f"  Liczba: {len(incognia_requests)}")
    for r in incognia_requests[:10]:
        print(f"  [{r['status']}] [{r['method']}] {r['url'][:150]}")

    print("\n=== HEADERS Z INCOGNIA ===")
    print(f"  Liczba: {len(headers_with_incognia)}")
    for h in headers_with_incognia[:5]:
        print(f"  {h['header']} ({h['value_len']} B) w {h['url']}")

    print("\n=== JWE TOKENS W RESPONSES ===")
    print(f"  Liczba: {len(jwe_tokens)}")
    for t in jwe_tokens[:5]:
        print(f"  [{t['status']}] {t['url']}  len={t['len']}")

    print("\n=== POST DO VINTED API ===")
    print(f"  Liczba: {len(vinted_api_posts)}")
    for p in vinted_api_posts[:15]:
        print(f"  [{p['status']}] {p['url']}")

    print("\n=== COOKIES Z INCOGNIA ===")
    for c in report["cookies_incognia_related"][:5]:
        print(f"  {c['url']}: {c['cookie']}")


if __name__ == "__main__":
    main()
