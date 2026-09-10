# coding: utf-8
"""Spike B4b: Dlaczego Incognia SDK nie ładuje się w Camoufox?

Sprawdzamy:
  - czy HTML zawiera <script src="...incognia...">
  - czy network widzi request do incognia
  - czy są jakieś błędy konsolowe przy ładowaniu SDK
  - czy po dłuższym oczekiwaniu SDK się pojawia
  - czy incognia SDK jest wstrzykiwane lazy (np. dopiero przy checkout)
"""
import json
import time
from pathlib import Path

from camoufox.sync_api import Camoufox

PROFIL = r"f:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"  # kanoniczny profil
ITEM_ID = 9807925466
OUTPUT = Path(r"C:\Temp\wynik_spike_B4b_incognia_loader.json")
ITEM_URL = f"https://www.vinted.pl/items/{ITEM_ID}"


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    findings = {}

    with Camoufox(headless=True, persistent_context=True,
                  user_data_dir=PROFIL, locale="pl-PL") as cf:
        page = cf.new_page() if hasattr(cf, "new_page") else cf.pages[0]

        # Łap requesty do incognia + błędy konsoli
        incognia_requests = []
        console_errors = []
        page_errors = []

        def on_request(req):
            try:
                url = req.url
                if "incognia" in url.lower() or "incognia" in req.headers.get("referer", "").lower():
                    incognia_requests.append({
                        "url": url, "method": req.method,
                        "resource_type": req.resource_type,
                        "headers_subset": {k: v for k, v in req.headers.items()
                                          if "incog" in k.lower() or "fingerprint" in k.lower()},
                    })
            except Exception:
                pass

        page.on("request", on_request)
        page.on("console", lambda msg: console_errors.append({"type": msg.type, "text": msg.text[:300]})
                if msg.type in ("error", "warning") else None)
        page.on("pageerror", lambda exc: page_errors.append(str(exc)[:300]))

        print(f"[B4b] Otwieram {ITEM_URL}", flush=True)
        page.goto(ITEM_URL, wait_until="domcontentloaded", timeout=30000)

        # Sprawdź HTML pod kątem <script src="incognia...">
        html = page.content()
        import re
        script_srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html)
        findings["script_srcs_in_html"] = [s for s in script_srcs if "incognia" in s.lower()]
        findings["incognia_inline_script_present"] = "incognia-sdk" in html.lower() or "incognia.com" in html.lower()
        # Szukaj w kontekście INCOGNIA_WEB_CLIENT_SIDE_KEY
        idx = html.find("INCOGNIA_WEB_CLIENT_SIDE_KEY")
        if idx >= 0:
            # Szukamy skryptu/inline-scriptu wokół
            before = html[max(0, idx-500):idx]
            after = html[idx:idx+1000]
            findings["around_incognia_key"] = {
                "before_end": before[-300:],
                "after": after[:500],
            }

        # Poczekaj i sprawdź czy SDK się załadował
        time.sleep(10)
        sdk = page.evaluate("""
() => {
  const all = Object.getOwnPropertyNames(window);
  return {
    has_Incognia: typeof window.Incognia,
    has_incognia: typeof window.incognia,
    has_IncogniaSDK: typeof window.IncogniaSDK,
    has_IncogniaWeb: typeof window.IncogniaWeb,
    incog_related: all.filter(k => /incog/i.test(k)),
    ddjskey: window.ddjskey,
    incognia_key_in_html: !!document.querySelector('script[src*="incognia"]'),
  };
}
""")
        findings["after_10s"] = sdk

        # Sprawdź czy na stronie jest iframe (Incognia czasem ładuje iframe)
        iframe_info = page.evaluate("""
() => {
  const iframes = Array.from(document.querySelectorAll('iframe')).map(f => ({
    src: f.src, id: f.id, name: f.name,
  }));
  return {iframe_count: iframes.length, iframes: iframes.slice(0, 10)};
}
""")
        findings["iframes"] = iframe_info

        # Sprawdź localStorage / sessionStorage - czy SDK zapisał tam cokolwiek
        storage = page.evaluate("""
() => {
  const ls = {};
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i);
    const v = localStorage.getItem(k);
    if (k && (k.includes('incog') || v.includes('incognia') || k.includes('datad'))) {
      ls[k] = v.substring(0, 200);
    }
  }
  const ss = {};
  for (let i = 0; i < sessionStorage.length; i++) {
    const k = sessionStorage.key(i);
    const v = sessionStorage.getItem(k);
    if (k && (k.includes('incog') || v.includes('incognia') || k.includes('datad'))) {
      ss[k] = v.substring(0, 200);
    }
  }
  return {localStorage: ls, sessionStorage: ss};
}
""")
        findings["storage_incog"] = storage

        findings["incognia_requests_count"] = len(incognia_requests)
        findings["incognia_requests"] = incognia_requests[:10]
        findings["console_errors_count"] = len(console_errors)
        findings["console_errors"] = console_errors[:10]
        findings["page_errors"] = page_errors[:5]

    OUTPUT.write_text(json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[B4b] Zapisano {OUTPUT}", flush=True)

    print("\n=== PODSUMOWANIE B4b ===", flush=True)
    print(f"  Script src z 'incognia' w HTML: {findings.get('script_srcs_in_html')}", flush=True)
    print(f"  Incognia inline obecny: {findings.get('incognia_inline_script_present')}", flush=True)
    print(f"  Incognia requests: {findings.get('incognia_requests_count')}", flush=True)
    print(f"  Console errors: {findings.get('console_errors_count')}", flush=True)
    print(f"  Page errors: {findings.get('page_errors')}", flush=True)
    print(f"  After 10s SDK: {json.dumps(findings.get('after_10s', {}), indent=2)}", flush=True)
    print(f"  iframes: {findings.get('iframes')}", flush=True)
    print(f"  storage_incog: {json.dumps(findings.get('storage_incog', {}), indent=2)}", flush=True)


if __name__ == "__main__":
    main()
