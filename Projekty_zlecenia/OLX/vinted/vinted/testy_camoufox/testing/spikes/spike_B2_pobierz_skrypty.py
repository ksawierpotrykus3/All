# coding: utf-8
"""Spike B2: Pobranie wybranych skryptów z Vinted CDN do lokalnej analizy.

Źródło listy URL-i: wynik_spike_B1_lista_skryptow.json.

Priorytet pobrania:
  P0: /gtg/* (4 pliki po ~180 KB - prawdopodobnie Incognia SDK + DataDome bootstrap)
  P0: /datadome/5.9.2/tags.js (oficjalny DataDome SDK)
  P1: marketplace-web-assets/_next/static/chunks/*.js (główny bundle React)
  P2: cookielaw (OneTrust - mało istotne dla checkout/build, pomijamy)

Dodatkowo:
  - obserwacja, czy nagłówki (Accept, User-Agent) wpływają na payload
  - pomiar czasu pobrania każdego pliku
  - hash SHA256 dla każdego pliku
  - nagłówki response (Cache-Control, ETag, Server) dla późniejszej analizy
"""
import hashlib
import json
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlparse

from curl_cffi import requests as creq

PROFIL = r"f:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"  # kanoniczny profil
OUTPUT_DIR = Path(r"C:\Temp\vinted_scripts")
MANIFEST = Path(r"C:\Temp\wynik_spike_B2_manifest.json")


def wczytaj_cookies(profil: str) -> dict:
    cookies = {}
    db = Path(profil) / "cookies.sqlite"
    if not db.exists():
        return cookies
    conn = sqlite3.connect(str(db))
    try:
        cur = conn.execute("SELECT name, value FROM moz_cookies WHERE host LIKE '%vinted.pl%'")
        for n, v in cur.fetchall():
            cookies[n] = v
    finally:
        conn.close()
    return cookies


def safe_filename(url: str) -> str:
    """Zamienia URL na bezpieczną nazwę pliku."""
    p = urlparse(url)
    path = p.path.strip("/").replace("/", "_").replace("?", "_q_")
    domain = p.netloc.replace(".", "_").replace(":", "_p_")
    if not path:
        path = "root"
    return f"{domain}_{path}.js"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def pobierz(url: str, cookies: dict, impersonate: str = "chrome131") -> dict:
    """Pobiera URL przez curl_cffi i zwraca metadane."""
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0",
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "referer": "https://www.vinted.pl/items/9807925466",
    }
    t0 = time.monotonic()
    try:
        r = creq.get(url, headers=headers, cookies=cookies, impersonate=impersonate, timeout=30)
        elapsed = round((time.time() - t0) * 1000, 1)
        if r.status_code == 200:
            return {
                "url": url, "status": 200, "elapsed_ms": elapsed,
                "size": len(r.content), "sha256": sha256_bytes(r.content),
                "content_type": r.headers.get("content-type", ""),
                "headers_subset": {k: r.headers.get(k) for k in
                                   ("server", "cache-control", "etag", "age", "x-cache")},
                "body": r.content,
            }
        return {"url": url, "status": r.status_code, "elapsed_ms": elapsed,
                "body_preview": r.text[:400] if r.text else ""}
    except Exception as e:
        return {"url": url, "status": None, "elapsed_ms": round((time.time() - t0) * 1000, 1),
                "error": repr(e)}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    cookies = wczytaj_cookies(PROFIL)
    print(f"[B2] Załadowano {len(cookies)} cookies z profilu", flush=True)

    # URL-e z B1 - wyselekcjonowane P0 i P1
    urls_p0 = [
        "https://www.vinted.pl/gtg/",
        "https://www.vinted.pl/gtg/Mk7G4bHiTzGE9cDjzSnmGGX65Y_rbna8UHfRpJAD9mSDI8Bc",
        "https://www.vinted.pl/gtg/Mk6e_LHgYXjj-KWfylWdBmuXmqnddXbiCmCa_tAL_WiXJMH55MBc",
        "https://www.vinted.pl/gtg/Mk6e_LHgYXjj_t-FxV_kaWX5-t-hdXbiCmCa_tAL_WiXJMH55MBc",
        "https://static-assets.vinted.com/datadome/5.9.2/tags.js",
    ]

    # Marketplace chunks - wszystkie z _next/static/chunks
    urls_p1_base = "https://marketplace-web-assets.vinted.com"
    # Weź wszystkie ścieżki z B1 (wyciągniemy w load)
    import json as _json
    b1 = _json.loads(Path(r"C:\Temp\wynik_spike_B1_lista_skryptow.json").read_text(encoding="utf-8"))
    urls_p1 = sorted({s["url"] for s in b1["scripts_by_url"]
                      if "marketplace-web-assets" in s.get("domain", "")})

    print(f"[B2] P0 URLs: {len(urls_p0)}, P1 (chunks): {len(urls_p1)}", flush=True)

    manifest = {
        "started": time.strftime("%Y-%m-%d %H:%M:%S"),
        "cookies_count": len(cookies),
        "files": [],
    }

    # P0 - pełne pobranie
    for url in urls_p0:
        print(f"[B2] P0: {url}", flush=True)
        result = pobierz(url, cookies)
        entry = {k: v for k, v in result.items() if k != "body"}
        if "body" in result:
            fname = safe_filename(url)
            fpath = OUTPUT_DIR / fname
            fpath.write_bytes(result["body"])
            entry["local_path"] = str(fpath)
            entry["local_filename"] = fname
            print(f"     -> {result['size']} B -> {fname}", flush=True)
        manifest["files"].append(entry)

    # P1 - tylko top 10 największych (oszczędność transferu, mamy ich 75)
    # Odfiltruj P1 - sortuj po content_length z B1
    b1_sorted = sorted(
        [s for s in b1["scripts_by_url"] if "marketplace-web-assets" in s.get("domain", "")],
        key=lambda x: x.get("content_length", 0), reverse=True,
    )
    urls_p1_top = [s["url"] for s in b1_sorted[:15]]
    for url in urls_p1_top:
        print(f"[B2] P1: {url}", flush=True)
        result = pobierz(url, cookies)
        entry = {k: v for k, v in result.items() if k != "body"}
        if "body" in result:
            fname = safe_filename(url)
            fpath = OUTPUT_DIR / fname
            fpath.write_bytes(result["body"])
            entry["local_path"] = str(fpath)
            entry["local_filename"] = fname
            print(f"     -> {result['size']} B -> {fname}", flush=True)
        manifest["files"].append(entry)

    manifest["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    manifest["total_files"] = len(manifest["files"])
    manifest["total_bytes"] = sum(f.get("size", 0) for f in manifest["files"])
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n[B2] Zapisano {manifest['total_files']} plików "
          f"({manifest['total_bytes']} B) do {OUTPUT_DIR}", flush=True)
    print(f"[B2] Manifest: {MANIFEST}", flush=True)


if __name__ == "__main__":
    main()
