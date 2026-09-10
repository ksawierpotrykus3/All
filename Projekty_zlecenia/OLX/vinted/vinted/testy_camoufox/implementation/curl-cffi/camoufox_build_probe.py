# coding: utf-8
"""camoufox_build_probe.py — czy build przez PRAWDZIWA przegladarke (Camoufox)
przechodzi na tym IP w trakcie blokady curl_cffi?

Jesli build 200 -> blokada dotyczy tylko curl_cffi (TLS fingerprint), hybryda dziala.
Jesli 403   -> blokada IP niezalezna od klienta, trzeba VPN/proxy lub czekac.

Uzycie: python camoufox_build_probe.py [item_id]
"""
import json
import sys
import time
from pathlib import Path

from camoufox import Camoufox
from curl_cffi import requests as cr

BASE_DIR = Path(__file__).resolve().parent
PROFILE_DIR = BASE_DIR.parent / "browser-profiles" / "profil_firefox_135"  # kanoniczny profil
CSRF = "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
ANON = "98c6af5a-87da-45f2-9be5-24cf9345b003"

# usun stale locki po hard-stopie (profil nalezny do tego projektu)
for lock in ("parent.lock", "lock", "lockfile"):
    p = PROFILE_DIR / lock
    try:
        if p.exists():
            p.unlink()
    except Exception:
        pass


def pick_item() -> int:
    s = cr.Session()
    try:
        for c in json.loads((BASE_DIR / "cookies_profil.json").read_text(encoding="utf-8")):
            try:
                s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/"))
            except Exception:
                pass
        s.headers.update({"accept": "application/json", "locale": "pl-PL",
                          "origin": "https://www.vinted.pl", "referer": "https://www.vinted.pl/"})
        r = s.get("https://www.vinted.pl/api/v2/catalog/items"
                  "?catalog_ids%5B%5D=44&price_to=100&order=newest_first&page=1&per_page=40&currency=PLN",
                  headers={"x-csrf-token": CSRF, "x-anon-id": ANON}, impersonate="chrome146", timeout=30)
        for it in r.json().get("items", []):
            if it.get("status") == "sold" or it.get("is_visible") is False:
                continue
            return it["id"]
    except Exception as e:
        print(f"BLAD wyboru itemu: {e}")
    return 0


def main():
    item_id = int(sys.argv[1]) if len(sys.argv) > 1 else pick_item()
    print(f"item_id={item_id}", flush=True)
    captured = {"requests": []}

    def on_response(resp):
        if resp.url.endswith("/api/v2/purchases/checkout/build"):
            captured["status"] = resp.status
            if resp.status == 200:
                try:
                    j = resp.json()
                    captured["checkout_id"] = (j.get("checkout") or {}).get("id")
                except Exception:
                    pass

    def on_request(req):
        if "checkout/build" in req.url or "conversations" in req.url:
            captured["requests"].append(f"{req.method} {req.url[:110]}")

    with Camoufox(
        persistent_context=True,
        headless=True,
        user_data_dir=str(PROFILE_DIR),
        os="windows",
        fingerprint_preset=True,
        humanize=True,
        block_webgl=True,
        i_know_what_im_doing=True,
    ) as ctx:
        page = ctx.new_page()
        page.on("response", on_response)
        page.on("request", on_request)
        try:
            page.goto(f"https://www.vinted.pl/items/{item_id}", wait_until="commit", timeout=45000)
        except Exception as e:
            print(f"goto err: {e}", flush=True)
        time.sleep(6)
        # diagnostyka strony: co sie w ogole zaladowalo
        try:
            diag = page.evaluate("""() => {
                const btns = [];
                document.querySelectorAll('button').forEach(b => {
                    const t = (b.textContent || '').trim().slice(0, 30);
                    const tid = b.getAttribute('data-testid') || '';
                    if (/buy|kup|checkout/i.test(tid + ' ' + t)) {
                        const r = b.getBoundingClientRect();
                        btns.push({tid, t, w: Math.round(r.width), h: Math.round(r.height)});
                    }
                });
                return {
                    title: document.title,
                    url: location.href,
                    buyBtn: !!document.querySelector('button[data-testid="item-buy-button"]'),
                    ddCaptcha: !!document.querySelector('.datadome-captcha, [class*="datadome"]'),
                    btns,
                };
            }""")
            print(f"DIAG: {json.dumps(diag, ensure_ascii=False)[:1200]}", flush=True)
        except Exception as e:
            print(f"diag err: {e}", flush=True)
        time.sleep(1)
        # dismiss OneTrust
        try:
            page.evaluate("""() => {
                const b = document.querySelector('#onetrust-accept-btn-handler');
                if (b) b.click();
            }""")
        except Exception:
            pass
        time.sleep(1)
        # klik Kup teraz
        for attempt in range(1, 4):
            if "status" in captured:
                break
            try:
                clicked = page.evaluate("""() => {
                    const b = document.querySelector('button[data-testid="item-buy-button"]');
                    if (!b) return false;
                    b.click();
                    return true;
                }""")
                print(f"click attempt={attempt} clicked={clicked}", flush=True)
            except Exception as e:
                print(f"click err: {e}", flush=True)
            for _ in range(100):
                if "status" in captured:
                    break
                time.sleep(0.2)
            if "status" not in captured:
                time.sleep(2)

    print(f"BUILD_STATUS={captured.get('status')} checkout_id={captured.get('checkout_id')}", flush=True)
    print(f"requesty: {captured['requests'][-6:]}", flush=True)
    (BASE_DIR / "wynik_camoufox_build_probe.json").write_text(
        json.dumps(captured, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
