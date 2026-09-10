# coding: utf-8
"""Spike B1: Inwentaryzacja skryptów JS ładowanych na stronie przedmiotu Vinted.

Uruchamia Camoufox z istniejącym profilem (gdzie cookies są już zalogowane),
wchodzi na stronę przedmiotu, przechwytuje WSZYSTKIE requesty do plików .js,
mierzy rozmiary Content-Length, grupuje po domenie i zapisuje raport.

Cel: lista kandydatów do pobrania w B2 + zrozumienie skąd Vinted ładuje kod
(w tym potencjalnie Incognia SDK i DataDome payload).
"""
import json
import re
import sqlite3
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

from camoufox.sync_api import Camoufox

PROFIL = r"f:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"  # kanoniczny profil
ITEM_ID = 9807925466  # własny przedmiot (nie rezerwujemy cudzego!)
OUTPUT = Path(r"C:\Temp\wynik_spike_B1_lista_skryptow.json")
ITEM_URL = f"https://www.vinted.pl/items/{ITEM_ID}"


def collect_scripts(headless=True):
    """Zbiera wszystkie requesty do .js na stronie przedmiotu."""
    scripts = []
    with Camoufox(headless=headless, persistent_context=True,
                  user_data_dir=PROFIL, locale="pl-PL") as cf:
        page = cf.new_page() if hasattr(cf, "new_page") else cf.pages[0]
        # Przechwycimy response do zmierzenia Content-Length
        response_data = {}

        def on_response(resp):
            try:
                ct = resp.headers.get("content-type", "")
                url = resp.url
                if not url.lower().endswith(".js") and "javascript" not in ct:
                    return
                # Zbierz metadane
                parsed = urlparse(url)
                scripts.append({
                    "url": url,
                    "domain": parsed.netloc,
                    "path": parsed.path,
                    "method": resp.request.method,
                    "status": resp.status,
                    "content_type": ct,
                    "content_length": int(resp.headers.get("content-length", 0) or 0),
                    "resource_type": resp.request.resource_type,
                    "ts": round(time.time() * 1000),
                })
            except Exception as e:
                scripts.append({"url": "(parse-error)", "error": repr(e)})

        page.on("response", on_response)
        print(f"[B1] Otwieram {ITEM_URL} (headless={headless})", flush=True)

        try:
            page.goto(ITEM_URL, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"[B1] goto error: {e}", flush=True)

        # Poczekaj na załadowanie (sieciowy idle)
        try:
            page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            print("[B1] networkidle timeout - kontynuuję", flush=True)

        # Daj dodatkowe 5s na leniwe ładowanie
        time.sleep(5)

        # Sprawdźmy też ile jest aktywnych requestów przez window.performance
        try:
            perf_entries = page.evaluate("""
() => {
  const entries = performance.getEntriesByType('resource');
  return entries
    .filter(e => e.initiatorType === 'script' || /\\.js(\\?|$)/.test(e.name))
    .map(e => ({name: e.name, duration: e.duration, size: e.transferSize}))
}""")
        except Exception as e:
            perf_entries = [{"error": repr(e)}]

    return scripts, perf_entries


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    print("=== B1 HEADLESS ===", flush=True)
    scripts_h, perf_h = collect_scripts(headless=True)
    print(f"[B1] headless zebrano {len(scripts_h)} skryptów", flush=True)

    print("=== B1 HEADED ===", flush=True)
    scripts_d, perf_d = collect_scripts(headless=False)
    print(f"[B1] headed zebrano {len(scripts_d)} skryptów", flush=True)

    # Dedup po URL (może być ładowane dwukrotnie)
    seen = set()
    deduped = []
    for s in scripts_h + scripts_d:
        url = s.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append(s)

    # Grupuj po domenie
    by_domain = defaultdict(list)
    for s in deduped:
        by_domain[s["domain"]].append(s)

    # Posortuj po rozmiarze malejąco
    deduped.sort(key=lambda x: x.get("content_length", 0), reverse=True)

    # Wyciągnij podejrzane URL-e (Incognia, datadome, fingerprint, sdk, analytics)
    keyword_re = re.compile(
        r"incognia|datadome|fingerprint|sensor|analytics|telemetry|sdk|tracking",
        re.IGNORECASE,
    )
    suspicious = [s for s in deduped if keyword_re.search(s.get("url", "")) or
                  keyword_re.search(s.get("path", ""))]

    summary = {
        "item_url": ITEM_URL,
        "headless_count": len(scripts_h),
        "headed_count": len(scripts_d),
        "deduped_count": len(deduped),
        "domains": {d: len(lst) for d, lst in sorted(by_domain.items(),
                                                    key=lambda x: -len(x[1]))},
        "suspicious_count": len(suspicious),
        "total_bytes": sum(s.get("content_length", 0) for s in deduped),
    }

    report = {
        "started": time.strftime("%Y-%m-%d %H:%M:%S"),
        "summary": summary,
        "scripts_by_url": deduped,
        "scripts_suspicious": suspicious,
        "by_domain": {d: lst for d, lst in by_domain.items()},
        "perf_entries_headless": perf_h[:50],
        "perf_entries_headed": perf_d[:50],
    }

    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    print(f"\n[B1] Zapisano {OUTPUT}", flush=True)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    print(f"\n[B1] Top 10 największych skryptów:", flush=True)
    for s in deduped[:10]:
        print(f"  {s.get('content_length', 0):>9} B  {s.get('status', '?')}  "
              f"{s.get('domain', '?')}  {s.get('path', '?')[:80]}", flush=True)
    print(f"\n[B1] Podejrzane skrypty ({len(suspicious)}):", flush=True)
    for s in suspicious[:30]:
        print(f"  {s.get('content_length', 0):>9} B  {s.get('domain', '?')}  "
              f"{s.get('path', '?')[:80]}", flush=True)


if __name__ == "__main__":
    main()
