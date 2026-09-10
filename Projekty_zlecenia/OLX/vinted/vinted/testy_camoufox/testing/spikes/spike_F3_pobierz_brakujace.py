# coding: utf-8
"""Spike F3: Pobranie brakujących plików .js + głęboka analiza pod Incognia/axios.

Kluczowe odkrycie F2: pobrane pliki to głównie GTM/Next.js framework.
BRAKUJE: static-assets.vinted.com/ateam/2026-08-02-0945/script.js
i innych plików które real Firefox załadował, a Camoufox nie.
"""
import hashlib
import json
import sqlite3
import time
from pathlib import Path

from curl_cffi import requests as creq

PROFIL = r"f:\PROJEKTY\vinted\vinted\testy_camoufox\implementation\browser-profiles\profil_firefox_135"  # kanoniczny profil
OUTPUT_DIR = Path(r"C:\Temp\vinted_scripts_v2")
MANIFEST = Path(r"C:\Temp\wynik_spike_F3_manifest.json")


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
    from urllib.parse import urlparse
    p = urlparse(url)
    return (p.netloc + p.path).replace("/", "_").replace(":", "_p_").replace("?", "_q_") + ".js"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def pobierz(url: str, cookies: dict, impersonate: str = "chrome131") -> dict:
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
                "ct": r.headers.get("content-type", ""),
                "body": r.content,
            }
        return {"url": url, "status": r.status_code, "elapsed_ms": elapsed,
                "preview": r.text[:300] if r.text else ""}
    except Exception as e:
        return {"url": url, "status": None, "error": repr(e)}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    cookies = wczytaj_cookies(PROFIL)

    # URL-e które załadował real Firefox, ale nie pobraliśmy w B2
    # Focus na "ateam" (podejrzany - może bundle Vinted) + k7v3q2 + challenge-platform
    urls_priority = [
        "https://static-assets.vinted.com/ateam/2026-08-02-0945/script.js",  # PODEJRZANE!
        "https://k7v3q2.vinted.com/85d7e768568e.js",  # nowa subdomena
        "https://www.vinted.pl/cdn-cgi/challenge-platform/scripts/jsd/main.js",  # CF challenge
    ]

    # Dodatkowo: pobierz WSZYSTKIE marketplace chunks (te których nie mamy)
    # Z raportu F1 wyciągnij WSZYSTKIE _next/static/chunks/*.js
    f1 = json.loads(Path(r"C:\Temp\wynik_spike_F1_real_firefox.json").read_text(encoding="utf-8"))
    seen_in_b2 = set()
    for f in Path(r"C:\Temp\vinted_scripts").glob("*.js"):
        seen_in_b2.add(f.name)

    new_chunks = set()
    for url in f1.get("all_requests", []):
        url = url.get("url", "")
        if "_next/static/chunks/" in url and url.endswith(".js"):
            fname = safe_filename(url)
            if fname not in seen_in_b2:
                new_chunks.add(url)
    for url in f1.get("responses", []):
        url = url.get("url", "")
        if "_next/static/chunks/" in url and url.endswith(".js"):
            fname = safe_filename(url)
            if fname not in seen_in_b2:
                new_chunks.add(url)

    print(f"[F3] P0 URLs: {len(urls_priority)}, nowych chunków: {len(new_chunks)}", flush=True)

    manifest = {"started": time.strftime("%H:%M:%S"), "files": []}

    for url in urls_priority:
        print(f"[F3] P0: {url}", flush=True)
        result = pobierz(url, cookies)
        entry = {k: v for k, v in result.items() if k != "body"}
        if "body" in result:
            fname = safe_filename(url)
            fpath = OUTPUT_DIR / fname
            fpath.write_bytes(result["body"])
            entry["local_path"] = str(fpath)
            entry["local_filename"] = fname
            print(f"     -> {result['size']} B", flush=True)
        manifest["files"].append(entry)

    # Teraz top 30 największych nowych chunków (jeśli są)
    new_chunks_list = sorted(new_chunks)
    for url in new_chunks_list[:30]:
        print(f"[F3] CHUNK: {url}", flush=True)
        result = pobierz(url, cookies)
        entry = {k: v for k, v in result.items() if k != "body"}
        if "body" in result:
            fname = safe_filename(url)
            fpath = OUTPUT_DIR / fname
            fpath.write_bytes(result["body"])
            entry["local_path"] = str(fpath)
            entry["local_filename"] = fname
            print(f"     -> {result['size']} B", flush=True)
        manifest["files"].append(entry)

    manifest["finished"] = time.strftime("%H:%M:%S")
    manifest["total_files"] = len(manifest["files"])
    manifest["total_bytes"] = sum(f.get("size", 0) for f in manifest["files"])
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n[F3] Zapisano {manifest['total_files']} plików "
          f"({manifest['total_bytes']} B) do {OUTPUT_DIR}", flush=True)


if __name__ == "__main__":
    main()
