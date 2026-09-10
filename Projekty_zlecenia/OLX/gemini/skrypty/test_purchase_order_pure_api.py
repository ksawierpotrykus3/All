"""Deterministyczny test API: Tworzenie zamówienia zakupu (purchase-order) przez czysty curl_cffi.

Bez użycia przeglądarki, mierzy realny czas RTT i zapisuje dowód do gemini/dane/purchase_order_api_proof.json.
"""
import json
import time
from pathlib import Path
from curl_cffi import requests

BASE = Path(__file__).resolve().parent.parent.parent
DANE_DIR = BASE / "gemini" / "dane"
COOKIES_FILE = DANE_DIR / "cookies.json"

if not COOKIES_FILE.exists():
    raise SystemExit(f"Brak pliku {COOKIES_FILE}. Zaloguj się przez ZALOGUJ_SIE_OLX.bat.")

cookies = json.load(open(COOKIES_FILE, encoding="utf-8"))
token = next((c["value"] for c in cookies if c["name"] == "access_token"), None)

if not token:
    raise SystemExit("Brak access_token w cookies.json.")

# Testowa aktywna oferta
AD_ID = 1018987579
URL = "https://pl.ps.prd.eu.olx.org/order/v1/purchase-order"

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
    "Origin": "https://www.olx.pl",
    "Referer": "https://www.olx.pl/",
}

payload = {"adId": AD_ID}

t0 = time.perf_counter()
r = requests.post(URL, headers=headers, json=payload, impersonate="chrome124", timeout=15)
latency_ms = round((time.perf_counter() - t0) * 1000, 2)

proof = {
    "timestamp": time.time(),
    "url": URL,
    "method": "POST",
    "status_code": r.status_code,
    "latency_ms": latency_ms,
    "payload": payload,
    "headers_sent": {"Authorization": "Bearer [REDACTED]", "Content-Type": "application/json"},
    "response_headers": dict(r.headers),
    "response_body": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text,
}

out_path = DANE_DIR / "purchase_order_api_proof.json"
out_path.write_text(json.dumps(proof, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"Status: {r.status_code}")
print(f"Czas odpowiedzi (RTT): {latency_ms} ms")
print(f"Zapisano dowod do: {out_path}")
print(f"Odpowiedz: {proof['response_body']}")
