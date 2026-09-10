# -*- coding: utf-8 -*-
"""Skrypt zbierający 50 najnowszych ofert z IT i 50 z Serwisów ze wszystkimi danymi.

Struktura zapisu:
dane_badania/
  it/
    {id}_{slug}/
      zlecenie.txt
      zlecenie.json
      strona.html
  serwisy/
    {id}_{slug}/
      zlecenie.txt
      zlecenie.json
      strona.html
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from bs4 import BeautifulSoup
from playwright.sync_api import Page

import config
from browser_driver import BrowserDriver

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "dane_badania"
DATA_DIR.mkdir(parents=True, exist_ok=True)

CATEGORIES = [
    {
        "name": "it",
        "label": "Programowanie i IT",
        "url": "https://useme.com/pl/jobs/category/programowanie-i-it,35/"
    },
    {
        "name": "serwisy",
        "label": "Serwisy internetowe",
        "url": "https://useme.com/pl/jobs/category/serwisy-internetowe,34/"
    }
]


def sanitize_filename(name: str) -> str:
    s = re.sub(r'[^a-zA-Z0-9_\-\.]+', '_', name).strip('_')
    return s[:60] if s else "zlecenie"


def fetch_all_competitors(page: Page, job_id: str) -> List[Dict[str, Any]]:
    """Pobiera wszystkie strony konkurencji przez wewnętrzny endpoint Useme."""
    all_bids = []
    page_num = 1
    while True:
        try:
            res = page.evaluate(f"""async () => {{
                try {{
                    const r = await fetch('/pl/jobs/get-offers/{job_id}/?page={page_num}');
                    if (!r.ok) return null;
                    return await r.json();
                }} catch (e) {{
                    return null;
                }}
            }}""")
            if not res or not res.get("results"):
                break
            
            for item in res.get("results", []):
                tags = [t.get("name", "") for t in item.get("contractor_tags", []) if t.get("name")]
                deals = item.get("contractor_deals", 0)
                deals_str = f"{deals} umów" if deals != 1 else "1 umowa"
                all_bids.append({
                    "name": item.get("contractor_user", "Anonim"),
                    "profile_url": item.get("contractor_url", ""),
                    "deals": deals_str,
                    "created_on": item.get("created_on", ""),
                    "tags": tags,
                    "avatar": item.get("avatar", "")
                })

            total_pages = res.get("total_pages", 1)
            if page_num >= total_pages:
                break
            page_num += 1
        except Exception as e:
            print(f"        [WARN] Błąd pobierania strony {page_num} konkurencji dla {job_id}: {e}")
            break

    return all_bids


def extract_job_details(page: Page, job_url: str, job_id: str) -> Dict[str, Any]:
    """Pobiera pełne dane pojedynczego zlecenia i jego konkurencji."""
    page.goto(job_url, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(1500)

    # Rozwiń pełny opis jeśli zwinięty
    for sel in ["button:has-text('pokaż pełny opis')", ".job-details__show-more", "a:has-text('więcej')"]:
        try:
            btn = page.locator(sel).first
            if btn.count() > 0 and btn.is_visible():
                btn.click()
                page.wait_for_timeout(300)
                break
        except Exception:
            pass

    html = page.content()
    soup = BeautifulSoup(html, "html.parser")

    # Tytuł
    h1 = soup.select_one("h1")
    title = h1.get_text(strip=True) if h1 else "Bez tytułu"

    # Pola szczegółowe
    fields: Dict[str, str] = {}
    for it in soup.select(".jobs-summary__item"):
        label_el = it.select_one(".jobs-summary__item-label")
        if not label_el:
            continue
        label = label_el.get_text(strip=True)
        val_el = it.select_one(".jobs-summary__item-value, .jobs-summary__item-text")
        if val_el:
            paragraphs = [p.get_text(strip=True) for p in val_el.find_all(["p", "div"]) if p.get_text(strip=True)]
            if len(paragraphs) > 1 and "opis" in label.lower():
                val = "\n\n".join(dict.fromkeys(paragraphs))
            else:
                val = val_el.get_text(" ", strip=True)
            fields[label] = val

    # Tagi/umiejętności wymagane w zleceniu (jeśli są)
    job_tags = []
    tags_container = soup.select_one(".job-details__tags, .job-tags")
    if tags_container:
        job_tags = [t.get_text(strip=True) for t in tags_container.select(".job-tags__item, .tag") if t.get_text(strip=True)]

    # Konkurencja
    competitors = fetch_all_competitors(page, job_id)

    return {
        "id": job_id,
        "url": job_url,
        "title": title,
        "fields": fields,
        "job_tags": job_tags,
        "competitors_count": len(competitors),
        "competitors": competitors,
        "raw_html": html
    }


def format_text_file(data: Dict[str, Any]) -> str:
    """Formatuje czytelny plik tekstowy zlecenie.txt wg schematu użytkownika."""
    lines = [
        data["title"],
        "=" * len(data["title"]),
        f"URL: {data['url']}",
        ""
    ]

    # Kluczowe pola w czytelnej kolejności
    priority_order = [
        "Zleceniodawca",
        "Opis",
        "Opublikowano",
        "Kategoria",
        "Prawa autorskie",
        "Budżet",
        "Ważne przez"
    ]

    used_keys = set()
    for key in priority_order:
        if key in data["fields"]:
            lines.append(key)
            lines.append(data["fields"][key])
            lines.append("")
            used_keys.add(key)

    # Pozostałe pola zmienne per oferta (np. Miejsce wykonania, Ilość zdjęć itp.)
    for k, v in data["fields"].items():
        if k not in used_keys:
            lines.append(f"{k}:")
            lines.append(v)
            lines.append("")

    if data.get("job_tags"):
        lines.append("Wymagane umiejętności / tagi:")
        lines.append(", ".join(data["job_tags"]))
        lines.append("")

    # Konkurencja
    bids = data.get("competitors", [])
    lines.append(f"Wysłane oferty ({len(bids)})")
    lines.append("-" * 30)

    if not bids:
        lines.append("(Brak złożonych ofert)")
    else:
        for b in bids:
            line_user = f"[{b['name']} | {b['deals']}]({b['profile_url']}) - {b['created_on']}"
            lines.append(line_user)
            if b.get("tags"):
                for tag in b["tags"]:
                    lines.append(f"  * {tag}")
            lines.append("")

    return "\n".join(lines).strip() + "\n"


def collect_category_jobs(driver: BrowserDriver, cat_config: Dict[str, str], target_count: int = 50) -> None:
    cat_dir = DATA_DIR / cat_config["name"]
    cat_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n=======================================================")
    print(f"ROZPOCZYNAM POBIERANIE: {cat_config['label']} (Cel: {target_count} ofert)")
    print(f"=======================================================")

    page = driver.context.new_page()
    collected_urls: List[Dict[str, str]] = []

    # 1. Zbieranie listy ofert z kolejnych stron kategorii
    page_num = 1
    while len(collected_urls) < target_count:
        list_url = f"{cat_config['url']}?page={page_num}"
        print(f"Pobieranie listy ze strony {page_num}: {list_url}")
        page.goto(list_url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(2000)
        driver.dismiss_cookie_banner(page)

        soup = BeautifulSoup(page.content(), "html.parser")
        articles = soup.select("article.job")
        if not articles:
            print("Brak kolejnych artykułów – koniec stron.")
            break

        for art in articles:
            for a in art.select("a[href*='/jobs/']"):
                href = a.get("href", "")
                if "/jobs/category/" in href:
                    continue
                m = re.search(r',(\d+)/?$', href) or re.search(r'/jobs/(\d+)/?', href)
                if m:
                    job_id = m.group(1)
                    full_url = href if href.startswith("http") else f"https://useme.com{href}"
                    # Sprawdź czy już nie mamy tego ID
                    if not any(x["id"] == job_id for x in collected_urls):
                        slug_match = re.search(r'/jobs/([^,]+),', href)
                        slug = slug_match.group(1) if slug_match else f"job_{job_id}"
                        collected_urls.append({"id": job_id, "url": full_url, "slug": slug})
                    break
            if len(collected_urls) >= target_count:
                break

        page_num += 1

    print(f"\nZebrano {len(collected_urls)} linków do zleceń. Przechodzę do pobierania detali...")

    # 2. Pobieranie każdego zlecenia z osobna
    for idx, item in enumerate(collected_urls, start=1):
        job_id = item["id"]
        slug = item["slug"]
        job_url = item["url"]
        folder_name = f"{job_id}_{sanitize_filename(slug)}"
        job_dir = cat_dir / folder_name
        job_dir.mkdir(parents=True, exist_ok=True)

        print(f"[{cat_config['name'].upper()} {idx}/{len(collected_urls)}] #{job_id} ({slug[:30]})...", end="", flush=True)

        try:
            details = extract_job_details(page, job_url, job_id)
            
            # Zapis txt
            txt_content = format_text_file(details)
            with open(job_dir / "zlecenie.txt", "w", encoding="utf-8") as f:
                f.write(txt_content)

            # Zapis html
            with open(job_dir / "strona.html", "w", encoding="utf-8") as f:
                f.write(details["raw_html"])

            # Zapis json (bez surowego html dla czystości)
            json_data = dict(details)
            del json_data["raw_html"]
            with open(job_dir / "zlecenie.json", "w", encoding="utf-8") as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)

            print(f" OK (konkurentów: {details['competitors_count']})")
        except Exception as e:
            print(f" BŁĄD: {e}")

    page.close()


def main():
    start_t = time.time()
    print("=== START ZBIERANIA 100 OFERT DO DANYCH BADAWCZYCH ===")
    
    with BrowserDriver(headless=True) as driver:
        # Sprawdzenie sesji
        test_page = driver.context.new_page()
        test_page.goto("https://useme.com/pl/jobs/category/programowanie-i-it,35/", wait_until="domcontentloaded")
        driver.dismiss_cookie_banner(test_page)
        logged_in = driver.check_logged_in(test_page)
        print(f"Status sesji Useme: Zalogowany={logged_in}")
        test_page.close()

        for cat in CATEGORIES:
            collect_category_jobs(driver, cat, target_count=50)

    elapsed = round(time.time() - start_t, 1)
    print(f"\n=== ZAKOŃCZONO POMYŚLNIE W {elapsed}s ===")
    print(f"Dane zapisane w: {DATA_DIR}")


if __name__ == "__main__":
    main()
