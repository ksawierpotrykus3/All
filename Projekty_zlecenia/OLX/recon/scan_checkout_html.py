"""Przeszukaj surowy HTML strony checkout OLX pod kątem endpointów API i __NEXT_DATA__."""
import json
import re
from pathlib import Path

from curl_cffi import requests as creq

BASE = Path(__file__).resolve().parent.parent
HTML_OUT = BASE / "dane" / "checkout_page.html"
FIND_OUT = BASE / "dane" / "checkout_html_findings.json"

CHECKOUT_URL = "https://www.olx.pl/delivery/checkout/1084508890/"
IMP = "chrome124"


def main():
    s = creq.Session(impersonate=IMP)
    r = s.get(CHECKOUT_URL, timeout=30)
    html = r.text
    HTML_OUT.write_text(html, encoding="utf-8")
    print(f"HTML len: {len(html)}")

    findings = {}

    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if m:
        raw = m.group(1)
        print(f"[+] __NEXT_DATA__ znaleziony, len={len(raw)}")
        try:
            findings["__NEXT_DATA__"] = json.loads(raw)
        except Exception as e:
            findings["__NEXT_DATA__raw"] = raw[:5000]
            print(f"    (nie-JSON, zapisano surowy fragment) {e}")

    api_urls = set(re.findall(r'https?://[a-zA-Z0-9_\-./]+(?:api|delivery|checkout|payu|rock|transaction|purchase)[a-zA-Z0-9_\-./?=&{}:]*', html))
    findings["api_urls"] = sorted(api_urls)

    rel_api = set(re.findall(r'["\'](/[a-zA-Z0-9_\-./]*(?:api|delivery|checkout|payment|payu|rock)[a-zA-Z0-9_\-./?=&{}:]*)[\'"]', html))
    findings["relative_api_paths"] = sorted(rel_api)

    keywords = ["BuyWithDelivery", "rock", "checkout", "payment", "payu", "blik", "delivery", "transaction", "order"]
    kw_hits = {}
    for kw in keywords:
        c = html.lower().count(kw.lower())
        if c:
            kw_hits[kw] = c
    findings["keyword_hits"] = kw_hits

    FIND_OUT.write_text(json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n[+] Zapisano:", FIND_OUT)
    print("Keyword hits:", json.dumps(kw_hits, ensure_ascii=False))
    print("API URLs:", len(findings["api_urls"]))
    print("Relative API:", len(findings["relative_api_paths"]))


if __name__ == "__main__":
    main()