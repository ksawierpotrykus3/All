# -*- coding: utf-8 -*-
"""
TEST 13 – Parser detalu oferty Useme (WYNIK BADAŃ TURY 3)
=====================================================================
KLUCZOWE USTALENIE (zweryfikowane empirycznie 2026-08-06):
  * page.evaluate + fetch na detalu -> ZAWSZE 403 Cloudflare challenge
    (nawet z tej samej sesji/kontekstu, w którym page.goto działa).
    "Surowy HTML" z testu 10 (~5,9 KB) to była strona challenge, nie detal.
  * page.goto (nawigacja) na detal -> DZIAŁA (Firefox headless + networkidle).
    Prawdziwy detal ma ~380 KB i zawiera server-rendered JSON-LD JobPosting
    oraz sekcję div.jobs-summary__item (label+value).

Dlatego parser działa na HTML-u z page.goto (jedyny realnie dostępny),
a selektory oparte są na JSON-LD + jobs-summary (struktura server-side).

BEZPIECZEŃSTWO: skrypt TYLKO czyta i parsuje – NIE wysyła żadnych ofert.
"""
import io, sys, json, os, re, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from bs4 import BeautifulSoup

TEST_DIR = r"c:\Users\Ksawier\Pictures\Screenshots\useme\lab\test13_parser_surowe_html"
OFFERS_JSON = r"c:\Users\Ksawier\Pictures\Screenshots\useme\lab\test10_flow_v2\intermediate\parsed_offers.json"
COOKIES_PATH = r"c:\Users\Ksawier\Pictures\Screenshots\useme\useme-ai-automation\cookies.json"
OUT_JSON = os.path.join(TEST_DIR, "parsed_details_v3.json")
USEME_BASE = "https://useme.com"

CF_MARKERS = ("Just a moment", "cf_chl", "challenges.cloudflare.com",
              "cf-turnstile", "Performing security verification")

# ============================================================================
# 1. DETEKCJA CLOUDFLARE
# ============================================================================

def is_cloudflare(html):
    if not html:
        return True
    head = html[:4000]
    return any(m in head for m in CF_MARKERS)

# ============================================================================
# 2. PARSER DETALU – JSON-LD (JobPosting) + jobs-summary
# ============================================================================

def get_ld_jobposting(soup):
    """Zwraca dict JSON-LD typu JobPosting (server-rendered) lub None."""
    for b in soup.select("script[type='application/ld+json']"):
        txt = b.get_text(strip=True)
        if not txt:
            continue
        try:
            data = json.loads(txt)
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            for d in data:
                if isinstance(d, dict) and d.get("@type") == "JobPosting":
                    return d
        elif isinstance(data, dict) and data.get("@type") == "JobPosting":
            return data
    return None


def summary_value(soup, label_text):
    """Znajduje div.jobs-summary__item o podanym labelu i zwraca wartość."""
    for item in soup.select(".jobs-summary__item"):
        label = item.select_one(".jobs-summary__item-label")
        if label and label_text.lower() in label.get_text(strip=True).lower():
            val = item.select_one(".jobs-summary__item-value") or item.select_one(".jobs-summary__item-text")
            if val:
                return re.sub(r"\s+", " ", val.get_text(" ", strip=True)).strip()
    return ""


def parse_offer_detail(html, source_url=""):
    """Parsuje detal oferty. Zwraca dict z polami mechanizmu."""
    if is_cloudflare(html):
        return {"status": "cloudflare", "source_url": source_url}

    soup = BeautifulSoup(html, "html.parser")
    ld = get_ld_jobposting(soup)
    detail = {
        "status": "ok",
        "source_url": source_url,
        "ld_json": bool(ld),
        "offer_id": ld.get("identifier", {}).get("value", "") if ld else "",
    }

    # ---- Tytuł: JSON-LD -> h1.jobs__page-title -> og:title ----
    title = (ld or {}).get("title", "") or ""
    if not title:
        h1 = soup.select_one("h1.jobs__page-title") or soup.select_one("h1")
        if h1:
            title = h1.get_text(" ", strip=True)
    if not title:
        og = soup.select_one("meta[property='og:title']")
        if og and og.get("content"):
            title = og["content"].replace(" - sprawdź to ogłoszenie", "").strip()
    detail["title"] = title or "?"

    # ---- Pełny opis: "Opis" + "Wymagane funkcje" (jobs-summary) ----
    desc_short = summary_value(soup, "Opis")
    desc_extra = summary_value(soup, "Wymagane funkcje")
    full = "\n\n".join(x for x in (desc_short, desc_extra) if x)
    if not full and ld:
        d = ld.get("description", "")
        full = re.sub(r"<[^>]+>", "", d) if isinstance(d, str) else ""
    detail["full_desc"] = full[:3000] if full else "?"

    # ---- Budżet: JSON-LD baseSalary -> "Budżet" ----
    budget = ""
    if ld and ld.get("baseSalary"):
        bs = ld["baseSalary"]
        val = bs.get("value")
        if isinstance(val, dict):
            val = val.get("value")
        cur = bs.get("currency", "")
        if val is not None:
            budget = f"{val} {cur}".strip()
            budget = budget.replace(".0 ", " ").replace(".0", "")
    if not budget:
        budget = summary_value(soup, "Budżet")
    detail["budget"] = budget or "Do negocjacji"

    # ---- Kategoria: "Kategoria" -> breadcrumb a[href*='/category/'] (ostatni) ----
    category = summary_value(soup, "Kategoria")
    if not category:
        cats = [a.get_text(strip=True) for a in soup.select("a[href*='/jobs/category/']")]
        category = cats[-1] if cats else ""
    detail["category"] = category or "?"

    # ---- Autor: JSON-LD hiringOrganization -> "Zleceniodawca" ----
    author = ""
    if ld and isinstance(ld.get("hiringOrganization"), dict):
        author = ld["hiringOrganization"].get("name", "")
    if not author:
        author = summary_value(soup, "Zleceniodawca")
    detail["author"] = author or "?"

    # ---- Opublikowano: "Opublikowano" -> JSON-LD datePosted ----
    published = summary_value(soup, "Opublikowano")
    if not published and ld and ld.get("datePosted"):
        published = ld["datePosted"]
    detail["published"] = published or "?"

    # ---- Prawa autorskie / ważność / liczba ofert (pomocnicze) ----
    detail["copyright"] = summary_value(soup, "Prawa autorskie")
    detail["expires"] = summary_value(soup, "Ważne przez")

    m = re.search(r"Wysłane oferty\s*\((\d+)\)", html)
    detail["offers_count"] = int(m.group(1)) if m else None

    # ---- Umiejętności: NIE występują na detalu zlecenia (potwierdzone) ----
    skills = [a.get_text(strip=True) for a in soup.select("a[href*='/jobs/skill/']")]
    detail["skills"] = skills

    # ---- Kompletność pól kluczowych ----
    detail["complete"] = all(detail.get(k) and detail.get(k) != "?" for k in
                             ("title", "full_desc", "budget", "category", "author"))
    return detail

# ============================================================================
# 3. POBIERANIE DETALU: page.goto (nawigacja) – Firefox headless + networkidle
# ============================================================================

def fetch_detail_html(url, attempts=3):
    """page.goto na detal (nawigacja przechodzi przez CF; fetch nie).
    Zwraca HTML lub None. Retry przy blokadzie."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        try:
            with open(COOKIES_PATH, "r", encoding="utf-8") as f:
                cd = json.load(f)
            context.add_cookies(cd.get("cookies", cd))
        except Exception:
            pass
        page = context.new_page()
        html = None
        for i in range(1, attempts + 1):
            try:
                page.goto(url, wait_until="networkidle", timeout=45000)
                h = page.content()
                if is_cloudflare(h):
                    print(f"    [próba {i}/{attempts}] Cloudflare – ponawiam...")
                    page.wait_for_timeout(3000)
                    continue
                html = h
                break
            except Exception as e:
                print(f"    [próba {i}/{attempts}] błąd: {str(e)[:120]}")
                page.wait_for_timeout(2000)
        browser.close()
        return html

# ============================================================================
# 4. MAIN – parsowanie 5 ofert z parsed_offers.json
# ============================================================================

def main():
    with open(OFFERS_JSON, "r", encoding="utf-8") as f:
        offers = json.load(f)

    urls = [o["url"] for o in offers if o.get("url")][:5]
    print(f"Pobieram i parsuję {len(urls)} detali...\n")

    results = []
    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] {url}")
        html = fetch_detail_html(url)
        if html is None:
            print("    [FAIL] nie pobrano (Cloudflare po retry)")
            results.append({"source_url": url, "status": "fetch_failed"})
            continue
        parsed = parse_offer_detail(html, url)
        parsed["html_size"] = len(html)
        print(f"    status={parsed['status']} komplet={parsed.get('complete')} "
              f"tytuł='{parsed.get('title','?')[:60]}' budżet='{parsed.get('budget')}'")
        results.append(parsed)
        time.sleep(1.0)

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    ok = [r for r in results if r.get("status") == "ok"]
    complete = [r for r in ok if r.get("complete")]
    print(f"\nZapisano: {OUT_JSON}")
    print(f"Sparsowane: {len(ok)}/{len(results)}, kompletne (bez '?'): {len(complete)}")
    for r in ok:
        print(f"  - [{r.get('offer_id')}] {r.get('title','?')[:55]} | autor={r.get('author')} "
              f"| kat={r.get('category')} | budżet={r.get('budget')} | publ={r.get('published')}")

if __name__ == "__main__":
    main()
