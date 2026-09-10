# coding: utf-8
"""Spike: pełny flow zakupu z TRUSTED CLICK + capture incognia/checkout.

Odpowiada na pytania:
1. Czy po page.click() (trusted event) SDK Incognia w ogóle się ładuje?
2. Czy checkout/build jest wysyłany i z jakim statusem?
3. Jaki jest realny czas od kliknięcia do purchase_id?
"""
import json
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from vintedbot.checkout import _get_context, close_context

PROFIL = r"f:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"  # kanoniczny profil
ITEM_ID = 9807925466
ITEM_URL = f"https://www.vinted.pl/items/{ITEM_ID}"
OUTPUT = Path(__file__).resolve().parent / "wynik_spike_flow_checkout_incognia.json"

REQUESTS = []
RESPONSES = []
INCOGNIA_HITS = []


def on_request(req):
    u = req.url
    entry = {"method": req.method, "url": u, "post": req.post_data}
    if "incognia" in u.lower():
        INCOGNIA_HITS.append(entry)
        print(f"[INCOGNIA REQ] {req.method} {u}", flush=True)
    if "/purchases" in u or "checkout" in u or "anon" in u.lower():
        REQUESTS.append(entry)
        print(f"[REQ] {req.method} {u}" + (f"  DATA={req.post_data}" if req.post_data else ""), flush=True)


def on_response(resp):
    u = resp.url
    entry = {"url": u, "status": resp.status, "location": resp.headers.get("location", "")}
    if "incognia" in u.lower():
        INCOGNIA_HITS.append(entry)
        print(f"[INCOGNIA RESP] {resp.status} {u}", flush=True)
    if "/purchases" in u or "checkout" in u or "anon" in u.lower():
        RESPONSES.append(entry)
        print(f"[RESP] {resp.status} {u}" + (f"  LOC={entry['location']}" if entry['location'] else ""), flush=True)


def main() -> None:
    result = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
    t_global = time.monotonic()

    ctx, is_fresh = _get_context(PROFIL, os_name="windows")
    result["context_fresh"] = is_fresh
    page = ctx.new_page()
    page.on("request", on_request)
    page.on("response", on_response)

    # 1) goto item
    t0 = time.monotonic()
    page.goto(ITEM_URL, wait_until="domcontentloaded", timeout=90000)
    result["steps"].append({"step": "goto", "ms": round((time.monotonic() - t0) * 1000, 1)})
    print("item loaded", flush=True)

    # 2) czekaj na przycisk
    t0 = time.monotonic()
    try:
        page.wait_for_selector('button[data-testid="item-buy-button"]', timeout=20000)
        result["steps"].append({"step": "button_ready", "ms": round((time.monotonic() - t0) * 1000, 1)})
    except Exception as e:
        result["steps"].append({"step": "button_ready", "error": repr(e)})
        print("NO BUTTON", flush=True)

    # 3) Incognia przed klikiem
    pre = page.evaluate(
        """() => {
            const keys = [];
            for (const k in window) if (/incognia/i.test(k)) keys.push(k);
            return {keys, has: typeof window.Incognia !== 'undefined'};
        }"""
    )
    result["incognia_before_click"] = pre
    print("INCOGNIA przed klikiem:", pre, flush=True)

    # 4) TRUSTED CLICK (page.click, nie evaluate)
    t_click = time.monotonic()
    try:
        page.click('button[data-testid="item-buy-button"]', timeout=10000)
        result["steps"].append({"step": "click_trusted", "ms": round((time.monotonic() - t_click) * 1000, 1)})
        print("TRUSTED CLICK OK", flush=True)
    except Exception as e:
        result["steps"].append({"step": "click_trusted", "error": repr(e)})
        print("CLICK FAIL", flush=True)

    # 5) Incognia po kliku (SDK może ładować się warunkowo po rozpoczęciu flow)
    time.sleep(2)
    post = page.evaluate(
        """() => {
            const keys = [];
            for (const k in window) if (/incognia/i.test(k)) keys.push(k);
            return {keys, has: typeof window.Incognia !== 'undefined'};
        }"""
    )
    result["incognia_after_click"] = post
    print("INCOGNIA po kliku:", post, flush=True)

    # 6) czekaj na redirect /checkout z purchase_id
    deadline = time.monotonic() + 25
    found_url = None
    while time.monotonic() < deadline:
        if "/checkout?" in page.url and "purchase_id=" in page.url:
            found_url = page.url
            break
        time.sleep(0.2)

    t_end = time.monotonic()
    if found_url:
        q = parse_qs(urlparse(found_url).query)
        result["steps"].append({
            "step": "reservation_success",
            "click_to_redirect_ms": round((t_end - t_click) * 1000, 1),
            "purchase_id": q.get("purchase_id", [""])[0],
            "order_id": q.get("order_id", [""])[0],
            "url": found_url,
        })
        print(f"SUCCESS purchase_id={q.get('purchase_id', [''])[0]}", flush=True)
    else:
        result["steps"].append({"step": "reservation_timeout", "click_to_timeout_ms": round((t_end - t_click) * 1000, 1), "final_url": page.url})
        print(f"TIMEOUT, final url: {page.url}", flush=True)

    result["requests_purchases"] = REQUESTS
    result["responses_purchases"] = RESPONSES
    result["incognia_network_hits"] = INCOGNIA_HITS
    result["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Zapisano: {OUTPUT}", flush=True)

    page.close()
    close_context(PROFIL)


if __name__ == "__main__":
    main()
