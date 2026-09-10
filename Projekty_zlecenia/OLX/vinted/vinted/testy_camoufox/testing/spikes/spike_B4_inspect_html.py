# coding: utf-8
"""Spike B4 v2: Uproszczona inspekcja - gdzie fizycznie jest token Incognia.
Bez networkidle (Vinted ma ciągły polling, nigdy nie nadchodzi)."""
import json
import re
import time
from pathlib import Path

from camoufox.sync_api import Camoufox

PROFIL = r"f:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"  # kanoniczny profil
ITEM_ID = 9807925466
OUTPUT = Path(r"C:\Temp\wynik_spike_B4_inspect_html.json")
ITEM_URL = f"https://www.vinted.pl/items/{ITEM_ID}"


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    findings = {}

    with Camoufox(headless=True, persistent_context=True,
                  user_data_dir=PROFIL, locale="pl-PL") as cf:
        page = cf.new_page() if hasattr(cf, "new_page") else cf.pages[0]

        vinted_responses = []

        def on_response(resp):
            try:
                url = resp.url
                if "vinted.pl" in url or "vinted.com" in url:
                    vinted_responses.append({
                        "url": url,
                        "method": resp.request.method,
                        "status": resp.status,
                        "ct": resp.headers.get("content-type", ""),
                        "cl": int(resp.headers.get("content-length", 0) or 0),
                    })
            except Exception:
                pass

        page.on("response", on_response)

        print(f"[B4] Otwieram {ITEM_URL}", flush=True)
        page.goto(ITEM_URL, wait_until="domcontentloaded", timeout=30000)
        # TYLKO 5s czekania - bez networkidle!
        time.sleep(8)

        # 1) Sprawdź HTML
        html_content = page.content()
        findings["html_size"] = len(html_content)
        findings["html_has_incognia"] = "incognia" in html_content.lower()
        findings["html_has_jwe"] = "JWE" in html_content
        findings["html_has_request_token"] = "x-incognia-request-token" in html_content.lower()
        findings["html_has_incognia_sdk"] = "incognia-sdk" in html_content.lower()

        # Szukaj długich base64-like stringów (JWE ~1800 znaków)
        long_b64 = re.findall(r'[A-Za-z0-9_\-]{800,2500}', html_content)
        findings["long_b64_count"] = len(long_b64)

        # 2) Sprawdź window
        window_inspect = page.evaluate("""
() => {
  const result = {};
  const candidates = [
    '__INITIAL_STATE__', '__NEXT_DATA__', '__APOLLO_STATE__',
    'IncogniaConfig', 'IncogniaSDK', 'incogniaToken',
    'Incognia', 'incognia', 'dataDomeOptions', 'DataDome',
    'dd', 'ddJs'
  ];
  for (const k of candidates) {
    const t = typeof window[k];
    if (t !== 'undefined') {
      try {
        const s = JSON.stringify(window[k]);
        result[k] = {type: t, len: s.length, preview: s.substring(0, 250)};
      } catch (e) {
        result[k] = {type: t, error: 'circular'};
      }
    }
  }
  // Specjalne: szukaj incognia gdziekolwiek
  const allKeys = Object.getOwnPropertyNames(window);
  result.incog_keys = allKeys.filter(k => /incog|finger|sensor/i.test(k));
  result.dd_keys = allKeys.filter(k => /dd|datad/i.test(k)).slice(0, 20);
  return result;
}
""")
        findings["window"] = window_inspect

        # 3) Jeśli jest incognia w HTML - wyciągnij kontekst
        if findings["html_has_incognia"]:
            idx = html_content.lower().find("incognia")
            findings["html_incognia_ctx"] = html_content[max(0, idx-150):idx+400]

        # 4) Poczekaj jeszcze 5s i sprawdź czy SDK się załadował
        time.sleep(5)
        sdk_status = page.evaluate("""
() => {
  const all = Object.getOwnPropertyNames(window);
  return {
    has_incognia: typeof window.Incognia,
    has_dd: typeof window.dd,
    incognia_related_keys: all.filter(k => /incog/i.test(k)),
    dd_related_keys: all.filter(k => /dd|datad/i.test(k)),
  };
}
""")
        findings["sdk_after_13s"] = sdk_status

        findings["vinted_responses_count"] = len(vinted_responses)
        findings["vinted_responses_sample"] = vinted_responses[:5]

    OUTPUT.write_text(json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[B4] Zapisano {OUTPUT}", flush=True)
    summary = {k: v for k, v in findings.items()
               if k in ("html_has_incognia", "html_has_jwe", "html_has_request_token",
                        "html_has_incognia_sdk", "long_b64_count",
                        "vinted_responses_count")}
    print(json.dumps(summary, indent=2, ensure_ascii=False), flush=True)

    if "incog_keys" in findings["window"]:
        print(f"\nWindow incog keys: {findings['window']['incog_keys']}", flush=True)
    if "dd_keys" in findings["window"]:
        print(f"Window dd keys: {findings['window']['dd_keys']}", flush=True)

    if findings["html_has_incognia"]:
        print(f"\nHTML incognia context: {findings.get('html_incognia_ctx', '')[:400]}", flush=True)


if __name__ == "__main__":
    main()
