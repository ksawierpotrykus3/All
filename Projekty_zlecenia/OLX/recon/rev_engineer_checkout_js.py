"""Reverse engineering checkoutu OLX: pobierz JS strony checkout i wyciągnij realne endpointy.

Metoda Vinted: analiza chunków JS → prawdziwe ścieżki API.
Nie wymaga logowania (pliki JS są publiczne).
"""
import json
import re
from pathlib import Path
from urllib.parse import urljoin

from curl_cffi import requests as creq

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "dane" / "checkout_js_endpoints.json"
CHECKOUT_URL = "https://www.olx.pl/delivery/checkout/1084508890/"

IMP = "chrome124"

API_RE = re.compile(
    r'["\'](/[a-zA-Z0-9_\-./]*(?:api|delivery|checkout|payment|payu|order|buy|rock|transaction|purchase)[a-zA-Z0-9_\-./?=&{}:]*)[\'"]'
)
URL_TEMPLATE_RE = re.compile(
    r'https?://[a-zA-Z0-9_\-./]+(?:api|delivery|checkout|payu|rock)[a-zA-Z0-9_\-./?=&{}:]*'
)


def extract_script_urls(html: str) -> list:
    urls = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html)
    return [urljoin(CHECKOUT_URL, u) for u in urls if u]


def extract_api_strings(text: str) -> set:
    found = set()
    for m in API_RE.finditer(text):
        s = m.group(1)
        if any(k in s.lower() for k in ("api", "delivery", "checkout", "payment", "payu", "order", "rock")):
            found.add(s)
    for m in URL_TEMPLATE_RE.finditer(text):
        found.add(m.group(0))
    return found


def main():
    s = creq.Session(impersonate=IMP)
    s.headers.update({"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36"})

    print(f"[*] Pobieram HTML: {CHECKOUT_URL}")
    html_resp = s.get(CHECKOUT_URL, timeout=20)
    print(f"    status: {html_resp.status_code}, len: {len(html_resp.text)}")

    script_urls = extract_script_urls(html_resp.text)
    seen = []
    for u in script_urls:
        if u not in seen:
            seen.append(u)
    print(f"[*] Znaleziono {len(seen)} skryptów")

    script_results = []

    for url in seen:
        if not any(k in url for k in ("olx", "olxeuweb")):
            continue
        try:
            r = s.get(url, timeout=30)
            if r.status_code != 200:
                continue
            text = r.text
            apis = extract_api_strings(text)
            if apis:
                entry = {"script": url, "len": len(text), "apis": sorted(apis)}
                script_results.append(entry)
                print(f"    [JS] {url.split('/')[-1][:60]} -> {len(apis)} ścieżek API")
        except Exception as e:
            print(f"    [ERR] {url}: {e}")

    all_findings = {
        "checkout_url": CHECKOUT_URL,
        "html_len": len(html_resp.text),
        "scripts_scanned": len(script_results),
        "scripts": script_results,
    }

    OUT.write_text(json.dumps(all_findings, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[+] Zapisano do {OUT}")
    print(f"[+] Łącznie przeanalizowano {len(script_results)} skryptów z endpointami")


if __name__ == "__main__":
    main()