# coding: utf-8
"""playwright_warm_path.py — CIEPLA sciezka przez fetch() w kontekscie strony.

Dlaczego fetch(): ctx.request (APIRequestContext) ma wlasny klient HTTP -> inny
fingerprint TLS niz Firefoks -> DataDome daje 403 (cookie wydane przez FF uzywane
przez obcy stack). fetch() w page.evaluate uzywa PRAWDZIWEGO stacku Firefoksa
(dokladnie jak frontend) -> DataDome nie widzi rozbieznosci.

Sciezka: bez nowej konwersacji (429 rate limit Vinted na POST /conversations),
od razu build na ISTNIEJACYM txn -> payment.

Warianty:
  no-load  : goto(commit) i od razu build+payment (bez czekania)
  with-load: goto + sleep 4 s
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR.parent / "implementation" / "browser-profiles" / "profil_firefox_135"  # kanoniczny (odblokowany sliderem)
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"
OUT = BASE_DIR / "wynik_playwright_warm_path.json"

TXN_ID = 21912438032  # z udanego bench_curl_gateway (10:48Z)


def wall():
    return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3] + "Z"


def find_checksum(obj):
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "checksum":
                hits.append(v)
            else:
                hits.extend(find_checksum(v))
    elif isinstance(obj, list):
        for v in obj:
            hits.extend(find_checksum(v))
    return hits


PAGE_FETCH_JS = """async (args) => {
    const opts = {method: args.method, headers: {'content-type': 'application/json',
        'x-csrf-token': args.csrf, 'x-anon-id': args.anon, 'accept': 'application/json'}};
    if (args.payload) opts.body = JSON.stringify(args.payload);
    const r = await fetch(args.url, opts);
    const t = await r.text();
    return {status: r.status, body: t.slice(0, 8000)};
}"""


def page_fetch(page, method, url, payload=None):
    return page.evaluate(PAGE_FETCH_JS, {
        "method": method, "url": url, "payload": payload, "csrf": CSRF, "anon": ANON})


def run_variant(page, name, results, wait_s):
    print(f"\n=== {name} ===", flush=True)
    entry = {}
    try:
        page.goto("https://www.vinted.pl/", wait_until="commit", timeout=45000)
    except Exception as e:
        print(f"goto err: {e}", flush=True)
    if wait_s:
        time.sleep(wait_s)

    t0 = time.monotonic()
    rb = page_fetch(page, "POST", "https://www.vinted.pl/api/v2/purchases/checkout/build",
                    {"purchase_items": [{"id": TXN_ID, "type": "transaction"}]})
    b_ms = round((time.monotonic() - t0) * 1000)
    entry["build"] = {"ms": b_ms, "status": rb["status"]}
    print(f"build: {b_ms} ms status={rb['status']}", flush=True)

    if rb["status"] == 200:
        try:
            bj = json.loads(rb["body"])
        except Exception:
            bj = {}
        cid = bj.get("checkout", {}).get("id")
        ch = find_checksum(bj)
        entry["checkout"] = cid
        t0 = time.monotonic()
        rp = page_fetch(page, "POST",
                        f"https://www.vinted.pl/api/v2/purchases/{cid}/checkout/payment",
                        {"checksum": ch[0] if ch else "", "payment_options": {"browser_info": {
                            "language": "pl", "color_depth": 24, "java_enabled": False,
                            "screen_height": 1080, "screen_width": 1920, "timezone_offset": -120}}})
        p_ms = round((time.monotonic() - t0) * 1000)
        entry["payment"] = {"ms": p_ms, "status": rp["status"]}
        print(f"payment: {p_ms} ms status={rp['status']}", flush=True)
        if rp["status"] == 200:
            try:
                pj = json.loads(rp["body"])
            except Exception:
                pj = {}
            entry["payment"]["payment_status"] = (pj.get("payment") or {}).get("status")
            entry["payment"]["redirect"] = \
                (((pj.get("action") or {}).get("parameters") or {}).get("url") or "")[:80]
            print(f"  -> {entry['payment']['payment_status']} {entry['payment']['redirect'][:50]}", flush=True)
        else:
            entry["payment"]["body"] = rp["body"][:150]
    else:
        entry["build"]["body"] = rb["body"][:150]
        print(f"  body: {entry['build']['body']}", flush=True)

    try:
        ck = page.context.cookies("https://www.vinted.pl/")
        d = next((c for c in ck if c.get("name") == "datadome"), None)
        entry["datadome_koniec"] = d["value"][:40] if d else "BRAK"
    except Exception:
        entry["datadome_koniec"] = "?"
    results[name] = entry


def main():
    from camoufox import Camoufox

    results = {"ts": wall()}

    for lock in ("parent.lock", "lock", "lockfile"):
        p = PROFILE_DIR / lock
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass

    prefs = {
        "layers.acceleration.disabled": True,
        "gfx.webrender.software": True,
        "gfx.webrender.all": False,
        "gfx.canvas.accelerated": False,
        "dom.ipc.processPrelaunch.enabled": False,
    }

    with Camoufox(
        persistent_context=True,
        headless=False,
        user_data_dir=str(PROFILE_DIR),
        os="windows",
        fingerprint_preset=True,
        humanize=False,
        block_webgl=True,
        firefox_user_prefs=prefs,
        i_know_what_im_doing=True,
    ) as ctx:
        page = ctx.new_page()
        run_variant(page, "no-load (wait 0s)", results, 0)
        run_variant(page, "with-load (wait 4s)", results, 4)

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nZapisano: {OUT}", flush=True)


if __name__ == "__main__":
    main()
