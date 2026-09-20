"""
TEST 15 – FINAL FLOW v3 (pełny mechanizm, DRY RUN – NIE wysyła ofert)
=====================================================================
Flow (ostateczny stack z testu 12: Chromium + playwright-stealth + cookies.json, headless=True):
  1. Lista:  page.goto(URL kategorii, domcontentloaded) + wait 3s + BeautifulSoup (article.job)
  2. L4:     page.evaluate + fetch na URL listy PO zakończeniu nawigacji – porównanie metod
  3. Marker: last_offer.txt (URL ostatniej oferty) – przy 2. uruchomieniu pomija przetworzone
  4. AI #1:  DeepSeek (localhost:4570/v1, deepseek-v4-pro) – selekcja 2-3 najwartościowszych ofert
  5. Detale: page.evaluate + fetch na URL detalu -> surowy HTML -> parser JSON-LD + CSS (details_v3/)
  6. AI #2:  POJEDYNCZO dla każdej oferty – propozycja z PEŁNYMI danymi detalu
  7. Zapis:  final_flow_results.json
  NIE WYSYŁA NICZEGO.
"""
import json
import os
import re
import sys
import time
from datetime import datetime
from bs4 import BeautifulSoup
import requests

# ============================================================================
# KONFIGURACJA
# ============================================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_FILE = os.path.join(OUTPUT_DIR, "final_flow_results.json")
LAST_OFFER_FILE = os.path.join(OUTPUT_DIR, "last_offer.txt")
COOKIES_PATH = os.path.join(OUTPUT_DIR, "cookies.json")
DETAILS_DIR = os.path.join(OUTPUT_DIR, "details_v3")
LIST_HTML_RENDERED = os.path.join(OUTPUT_DIR, "list_page_rendered.html")
LIST_HTML_RAW = os.path.join(OUTPUT_DIR, "list_page_raw_fetch.html")

USEME_BASE = "https://useme.com"
USEME_LIST_URL = "https://useme.com/pl/jobs/category/programowanie-i-it,35/"
DEEPSEEK_API_URL = "http://localhost:4570/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-v4-pro"
MAX_OFFERS = 12          # maks. liczba ofert pobranych z listy
MAX_DETAIL_OFFERS = 3    # AI #1 wybiera 2-3, stąd 3 detale
NAV_TIMEOUT = 45000      # ms dla page.goto

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(DETAILS_DIR, exist_ok=True)

T_START = time.time()

def timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log(msg):
    print(f"[{timestamp()}] {msg}")

def elapsed():
    return round(time.time() - T_START, 1)

# ============================================================================
# DEEPSEEK (endpoint OpenAI-compatible, przez requests)
# ============================================================================

def parse_ai_json_response(content):
    """Czyści odpowiedź AI i wyodrębnia JSON."""
    content = re.sub(r'<!-- PROXY_SID:.*?-->', '', content, flags=re.DOTALL).strip()
    if content.startswith("```"):
        lines = content.split("\n")
        start = 1 if lines[0].startswith("```") else 0
        end = -1 if lines[-1].startswith("```") else len(lines)
        content = "\n".join(lines[start:end]).strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {"raw_response": content, "parse_error": str(e)}

def call_deepseek(prompt, max_tokens=2000, temperature=0.7, timeout=150):
    """Wywołuje DeepSeek (localhost:4570) z TWARDYM watchdoggem (daemon-thread).
    Zwraca tekst odpowiedzi lub None przy timeout/zawieszeniu (flow leci dalej)."""
    import threading

    log(f"    [AI] zapytanie ({len(prompt)} znaków, model={DEEPSEEK_MODEL}, hard_timeout={timeout}s)...")

    def _post():
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": DEEPSEEK_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        try:
            resp = requests.post(DEEPSEEK_API_URL, json=payload, headers=headers, timeout=(10, timeout))
            resp.raise_for_status()
            ctype = resp.headers.get("Content-Type", "")
            if "text/event-stream" in ctype or resp.text.strip().startswith("data:"):
                full = ""
                for line in resp.text.split("\n"):
                    line = line.strip()
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            full += chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        except json.JSONDecodeError:
                            pass
                return full
            data = resp.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")
        except requests.exceptions.ConnectionError:
            log("    [ERROR] DeepSeek API nieosiągalne (localhost:4570)")
            raise
        except Exception as e:
            log(f"    [ERROR] DeepSeek API błąd: {e}")
            raise

    box = {}
    t = threading.Thread(target=lambda: box.update(result=_post()), daemon=True)
    t.start()
    t.join(timeout + 15)  # twardy limit
    if t.is_alive():
        log(f"    [ERROR] AI przekroczyło twardy limit {timeout}s – przerywam zapytanie")
        return None
    return box.get("result")

# ============================================================================
# PARSER LISTY (selektory z rundy 1 / test02)
# ============================================================================

def parse_offers_from_html(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    job_articles = soup.select("article.job")
    offers = []
    for article in job_articles:
        if len(offers) >= MAX_OFFERS:
            break
        try:
            offer = {}
            title_el = article.select_one("a.job__title-link")
            if title_el:
                offer["title"] = title_el.get_text(strip=True)
                href = title_el.get("href", "")
                offer["url"] = f"{USEME_BASE}{href}" if href.startswith("/") else href
            else:
                offer["title"] = None
                offer["url"] = None
            author_el = article.select_one("div.job__headline strong")
            offer["author"] = author_el.get_text(strip=True) if author_el else None
            offers_el = article.select_one("div.job__header-details--offers span:last-child")
            offer["offers_count"] = offers_el.get_text(strip=True) if offers_el else None
            date_el = article.select_one("div.job__header-details--date span:last-child")
            offer["expiry"] = date_el.get_text(strip=True) if date_el else None
            cat_el = article.select_one("div.job__category a p") or article.select_one("div.job__category")
            offer["category"] = cat_el.get_text(strip=True) if cat_el else None
            budget_el = article.select_one("span.job__budget-value")
            offer["budget"] = re.sub(r"\s+", " ", budget_el.get_text(strip=True)) if budget_el else None
            desc_el = article.select_one("div.job__content p")
            offer["description"] = desc_el.get_text(strip=True)[:300] if desc_el else None
            offers.append(offer)
        except Exception as e:
            log(f"    [WARN] błąd parsowania oferty: {e}")
            continue
    return offers

# ============================================================================
# PARSER DETALU v3 – JSON-LD (application/ld+json) + selektory CSS
# (test 13 nie istnieje -> parser bazowany na JSON-LD z surowego HTML + CSS)
# ============================================================================

CF_MARKERS = ("Just a moment", "cf_chl", "challenges.cloudflare.com", "cf-turnstile")

def is_cloudflare(html):
    if not html:
        return True
    head = html[:4000]
    return any(m in head for m in CF_MARKERS)

def _get_ld_json(html):
    """Zwraca listę obiektów z bloków script[type=application/ld+json]."""
    soup = BeautifulSoup(html, "html.parser")
    blocks = soup.select("script[type='application/ld+json'], script[type='application/json']")
    results = []
    for b in blocks:
        text = b.get_text(strip=True)
        if not text:
            continue
        try:
            data = json.loads(text)
            if isinstance(data, list):
                results.extend(data)
            else:
                results.append(data)
        except json.JSONDecodeError:
            continue
    return results

def _ld_find(ld_objs, keys):
    """Szuka pierwszej niepustej wartości dla listy kluczy w obiektach JSON-LD."""
    for obj in ld_objs:
        if not isinstance(obj, dict):
            continue
        for k in keys:
            v = obj.get(k)
            if isinstance(v, dict):
                v = v.get("@value") or v.get("name") or v.get("text") or ""
            if v and isinstance(v, str):
                return v.strip()
    return ""

def _first_text(soup, selectors, min_len=0):
    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            txt = el.get_text(" ", strip=True)
            txt = re.sub(r"\s+", " ", txt).strip()
            if txt and len(txt) >= min_len:
                return txt
    return ""

def parse_offer_detail_v3(html, source_url=""):
    """Parsuje detal (surowy HTML z evaluate+fetch LUB renderowany).
    Kolejność: JSON-LD (tytuł/opis/kategoria/budżet) -> selektory CSS."""
    if not html:
        return {"status": "empty", "source_url": source_url}
    if is_cloudflare(html):
        return {"status": "cloudflare", "source_url": source_url}

    soup = BeautifulSoup(html, "html.parser")
    ld_objs = _get_ld_json(html)
    ld_types = [o.get("@type") for o in ld_objs if isinstance(o, dict) and o.get("@type")]

    detail = {"status": "ok", "source_url": source_url, "ld_json_types": ld_types}

    # ---- Tytuł: JSON-LD (name/headline/title) -> h1 -> og:title ----
    title = _ld_find(ld_objs, ["name", "headline", "title"])
    if not title:
        title = _first_text(soup, ["h1", "h1[class*='title']", "meta[property='og:title']"])
        if title and soup.select_one("meta[property='og:title']"):
            title = soup.select_one("meta[property='og:title']").get("content", "").strip()
    detail["title"] = title or "?"

    # ---- Opis: JSON-LD (description) -> kontenery opisu ----
    desc = _ld_find(ld_objs, ["description", "text"])
    if not desc:
        desc = _first_text(soup, [
            "div.offer-content",
            "div.job-description",
            "div[class*='description']",
            "div[class*='offer-description']",
            "article",
            "div[class*='job-content']",
        ], min_len=20)
    detail["full_desc"] = desc[:3000] if desc else "?"

    # ---- Budżet: JSON-LD (baseSalary/priceSpecification) -> CSS ----
    budget = ""
    for obj in ld_objs:
        if not isinstance(obj, dict):
            continue
        bs = obj.get("baseSalary") or obj.get("priceSpecification") or {}
        if isinstance(bs, dict):
            v = bs.get("value") or bs.get("price")
            if v:
                budget = f"{v} {bs.get('currency', '')}".strip()
        if budget:
            break
    if not budget:
        budget = _first_text(soup, [
            "span.job__budget-value",
            "span[class*='budget']",
            "div[class*='budget']",
            "span[class*='price']",
        ])
        if not budget:
            # regex: "Budżet:" z kwotą
            body = soup.get_text(" ", strip=True)
            m = re.search(r"Budżet[^\d]{0,10}([\d\s.,]+\s*(?:PLN|zł|EUR|USD)?)", body)
            if m:
                budget = m.group(1).strip()
    detail["budget"] = budget or "Do negocjacji"

    # ---- Kategoria: JSON-LD (category) -> breadcrumbs -> linki /category/ ----
    category = _ld_find(ld_objs, ["category"])
    if not category:
        category = _first_text(soup, [
            "div.job__category",
            ".breadcrumb li:last-child",
            ".breadcrumb a:last-child",
            "a[href*='/category/']",
            "a[href*='/jobs/category/']",
        ])
    detail["category"] = category or "?"

    # ---- Autor: JSON-LD (hiringOrganization/author/publisher) -> CSS ----
    author = ""
    for obj in ld_objs:
        if not isinstance(obj, dict):
            continue
        for k in ("hiringOrganization", "author", "publisher"):
            v = obj.get(k)
            if isinstance(v, dict):
                author = v.get("name", "")
            elif isinstance(v, str):
                author = v
            if author:
                break
        if author:
            break
    if not author:
        author = _first_text(soup, [
            "div.job__headline strong",
            "a[class*='author']",
            "[class*='author-name']",
            ".user-name",
        ])
    detail["author"] = author or "?"

    # ---- Umiejętności / prawa autorskie (pomocnicze dla AI #2) ----
    skills = _first_text(soup, ["div.job__skills", "[class*='skill']", "a[href*='/jobs/skill/']"])
    detail["skills"] = skills if skills else ""
    copyright_ = _first_text(soup, ["[class*='copyright']"])
    if not copyright_:
        body = soup.get_text(" ", strip=True)
        if "przeniesienie praw autorskich" in body.lower():
            copyright_ = "Przeniesienie praw autorskich"
    detail["copyright"] = copyright_ if copyright_ else ""

    # ---- Kompletność ----
    detail["complete"] = all(detail.get(k) and detail.get(k) != "?" for k in
                            ("title", "full_desc", "budget", "category", "author"))
    return detail

# ============================================================================
# FETCH PRZEZ EVALUATE (same-origin)
# ============================================================================

def navigate_and_wait(page, url, wait_after=3000, max_cf_wait_s=18):
    """page.goto + domcontentloaded + czekanie. Jeśli Cloudflare (managed challenge)
    – czeka na auto-rozwiązanie (CF sam przeładowuje stronę). Zwraca page.content()."""
    page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
    page.wait_for_timeout(wait_after)
    t0 = time.time()
    while time.time() - t0 < max_cf_wait_s:
        html = page.content()
        if not is_cloudflare(html):
            return html
        page.wait_for_timeout(2500)
    return page.content()


def fetch_via_evaluate(page, url_path):
    """page.evaluate + fetch (same-origin, credentials include). Zwraca HTML lub None."""
    js_code = f"""
    async () => {{
        try {{
            const res = await fetch('{url_path}', {{credentials:'include'}});
            return await res.text();
        }} catch (e) {{
            return 'FETCH_ERROR: ' + e.message;
        }}
    }}
    """
    try:
        result = page.evaluate(js_code)
        if isinstance(result, str) and result.startswith("FETCH_ERROR"):
            log(f"    [ERROR] fetch JS error: {result[:200]}")
            return None
        return result
    except Exception as e:
        log(f"    [ERROR] evaluate+fetch nieudane: {str(e)[:200]}")
        return None

# ============================================================================
# MARKER (URL ostatniej oferty)
# ============================================================================

def check_marker_and_new(offers):
    """Marker = URL ostatniej oferty z poprzedniego uruchomienia.
    Zwraca (new_offers, marker_info)."""
    if not offers:
        return [], {"status": "no_offers"}
    last_url = offers[-1].get("url", "")
    marker_info = {"last_offer_url": last_url}

    if os.path.exists(LAST_OFFER_FILE):
        with open(LAST_OFFER_FILE, "r", encoding="utf-8") as f:
            saved_url = f.read().strip()
        marker_info["saved_url"] = saved_url
        # Znajdź pozycję markera w aktualnej liście (lista: najnowsze na górze)
        idx = next((i for i, o in enumerate(offers) if o.get("url") == saved_url), -1)
        if idx >= 0:
            new_offers = offers[:idx]  # oferty POWYŻEJ markera = nowsze
            marker_info["marker_found_at_index"] = idx
            marker_info["new_count"] = len(new_offers)
            marker_info["status"] = "found" if new_offers else "no_new"
        else:
            new_offers = offers
            marker_info["status"] = "not_found_all_new"
            marker_info["new_count"] = len(new_offers)
        log(f"[MARKER] zapisany URL: {saved_url[:80]}... -> status: {marker_info['status']}, nowych: {len(new_offers)}")
    else:
        new_offers = offers
        marker_info["status"] = "first_run"
        marker_info["new_count"] = len(offers)
        log("[MARKER] pierwsze uruchomienie – brak pliku markera, wszystkie oferty nowe")

    with open(LAST_OFFER_FILE, "w", encoding="utf-8") as f:
        f.write(last_url)
    marker_info["updated_url"] = last_url
    return new_offers, marker_info

# ============================================================================
# AI #1 – SELEKCJA (2-3 najwartościowsze)
# ============================================================================

def ai_select_offers(offers):
    simplified = []
    for i, o in enumerate(offers):
        simplified.append({
            "index": i,
            "title": o.get("title", ""),
            "category": o.get("category", ""),
            "budget": o.get("budget", ""),
            "author": o.get("author", ""),
            "offers_count": o.get("offers_count"),
            "description": (o.get("description", "") or "")[:300],
        })
    prompt = (
        "Jesteś doradcą dla freelancera-programisty Python specjalizującego się w web scrapingu, "
        "automatyzacji, API i integracjach. Poniżej lista ofert z polskiego portalu Useme "
        "(kategoria: Programowanie i IT).\n"
        "Wybierz 2-3 NAJBARDZIEJ WARTOŚCIOWE oferty dla tego profilu (dobre dopasowanie technologiczne, "
        "sensowny budżet/stawka, realny zakres). Uzasadnij każdy wybór po polsku.\n"
        "Zwróć TYLKO surowy JSON (bez markdown):\n"
        "{\n"
        '  "selected": [{"index": int, "title": str, "reason": str}],\n'
        '  "rejected": [{"index": int, "title": str, "reason": str}]\n'
        "}\n\n"
        "Lista ofert:\n" + json.dumps(simplified, ensure_ascii=False, indent=2)
    )
    try:
        response_text = call_deepseek(prompt, max_tokens=3000)
        if response_text is None:
            raise TimeoutError("AI #1 timeout (hard watchdog)")
        result = parse_ai_json_response(response_text)
        log(f"    [OK] AI #1 wybrała {len(result.get('selected', []))} ofert, odrzuciła {len(result.get('rejected', []))}")
        return result
    except Exception as e:
        log(f"    [WARN] AI #1 nieudane ({e}) – fallback: pierwsze {MAX_DETAIL_OFFERS} oferty")
        return {
            "selected": [{"index": i, "title": offers[i].get("title", ""), "reason": "Fallback (AI offline)"}
                         for i in range(min(MAX_DETAIL_OFFERS, len(offers)))],
            "rejected": [],
            "fallback": True,
            "error": str(e),
        }

# ============================================================================
# AI #2 – PROPOZYCJA (POJEDYNCZO, z pełnymi danymi detalu)
# ============================================================================

def ai_generate_proposal(offer, detail, seq, total):
    title = detail.get("title") or offer.get("title", "?")
    desc = detail.get("full_desc") or offer.get("description", "")
    budget = detail.get("budget") or offer.get("budget") or "Do negocjacji"
    category = detail.get("category") or offer.get("category", "")
    author = detail.get("author") or offer.get("author", "")
    skills = detail.get("skills", "")
    copyright_ = detail.get("copyright", "")

    log(f"  [AI #2 {seq}/{total}] generuję propozycję dla: {title[:70]}...")
    prompt = (
        "Jesteś freelancerem-programistą Python (web scraping, automatyzacja, API, integracje, "
        "przetwarzanie danych). Poniżej dane JEDNEJ konkretnej oferty z portalu Useme.\n"
        "Napisz PROFESJONALNĄ, KONKRETNĄ propozycję (4-8 zdań) odpowiedzi na TO zlecenie.\n"
        "WYMOGI – propozycja MUSI być konkretna, NIE generyczna:\n"
        "1. Odnieś się do 2-3 KONKRETNYCH elementów z opisu zlecenia (technologie, funkcje, wyzwania).\n"
        "2. Zaproponuj konkretny plan/zakres prac i ewentualnie harmonogram.\n"
        "3. NIE pisz ogólników typu 'chętnie podejmę się realizacji', 'proszę o doprecyzowanie'.\n"
        "4. Jeśli budżet to kwota – odnieś się do niej. Jeśli 'Do negocjacji' – zaproponuj realną "
        "stawkę (zł/h lub za całość) uzasadnioną zakresem.\n"
        "5. Język polski, ton profesjonalny ale przyjazny. Bez placeholdera [Imię].\n"
        "Zwróć TYLKO surowy JSON (bez markdown):\n"
        '{"proposal_text": str, "proposed_rate": str, "key_points": [str, str]}'
        "\n\nDANE OFERTY:\n"
        f"- Tytuł: {title}\n- Kategoria: {category}\n- Autor: {author}\n"
        f"- Budżet: {budget}\n- Umiejętności: {skills or 'brak danych'}\n"
        f"- Prawa autorskie: {copyright_ or 'brak danych'}\n"
        f"- PEŁNY OPIS:\n{desc[:3000]}"
    )
    try:
        response_text = call_deepseek(prompt, max_tokens=900, temperature=0.6)
        if response_text is None:
            raise TimeoutError("AI #2 timeout (hard watchdog)")
        result = parse_ai_json_response(response_text)
        if "proposal_text" not in result and "raw_response" in result:
            result = {"proposal_text": result["raw_response"], "proposed_rate": None, "key_points": []}
        return {"index": seq - 1, "title": title, "proposal": result, "generated_at": timestamp()}
    except Exception as e:
        log(f"    [ERROR] AI #2 nieudane: {e}")
        return {"index": seq - 1, "title": title,
                "proposal": {"proposal_text": f"[ERROR] {e}", "proposed_rate": None, "key_points": []},
                "error": str(e)}

# ============================================================================
# MAIN
# ============================================================================

def run_attempt(headless):
    """Wykonuje cały flow w danym trybie headless.
    Zwraca (exit_code, cf_blocked): cf_blocked=True sygnalizuje retry w trybie widocznym."""
    results = {
        "test": "TEST 15 – FINAL FLOW v3 (DRY RUN, nic nie wysłano)",
        "timestamp_start": timestamp(),
        "status": "IN_PROGRESS",
        "headless_mode": headless,
        "stack": "Chromium + playwright-stealth + cookies.json, domcontentloaded+3s",
        "steps": {},
    }

    print("=" * 72)
    print(f"  TEST 15 – FINAL FLOW v3 (DRY RUN) | headless={headless}")
    print("=" * 72)

    # ---- KROK 0: init Playwright ----
    try:
        from playwright.sync_api import sync_playwright
        from playwright_stealth import Stealth
    except ImportError as e:
        log(f"[FATAL] brak biblioteki: {e}")
        results["status"] = "FAIL"
        _save(results, attempt=headless)
        return 1, False

    playwright = browser = page = None
    try:
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        # cookies (sesja zalogowana – NIE modyfikujemy oryginału)
        with open(COOKIES_PATH, "r", encoding="utf-8") as f:
            cd = json.load(f)
        context.add_cookies(cd.get("cookies", cd))
        page = context.new_page()
        Stealth().apply_stealth_sync(page)
        results["steps"]["0_init"] = {"status": "OK", "browser": "chromium", "headless": headless}
        log(f"[OK] Playwright + Chromium + stealth + cookies (headless={headless})")
    except Exception as e:
        log(f"[FATAL] init Playwright: {e}")
        results["status"] = "FAIL"
        results["error"] = str(e)
        _save(results, attempt=headless)
        return 1, False

    try:
        # ═══════════════ KROK 1: LISTA (page.goto + BeautifulSoup) ═══════════════
        log("\n[KROK 1] Lista ofert: page.goto + BeautifulSoup...")
        t1 = time.time()
        rendered_html = None
        nav_attempts = 0
        nav_cf_seen = 0
        while rendered_html is None and nav_attempts < 3:
            nav_attempts += 1
            html = navigate_and_wait(page, USEME_LIST_URL)
            if is_cloudflare(html):
                nav_cf_seen += 1
                log(f"  [WARN] próba {nav_attempts}: nadal Cloudflare – ponawiam goto...")
                continue
            rendered_html = html
        if rendered_html is None:
            rendered_html = page.content()
        with open(LIST_HTML_RENDERED, "w", encoding="utf-8") as f:
            f.write(rendered_html)

        offers_bs = parse_offers_from_html(rendered_html)
        is_cf_list = is_cloudflare(rendered_html)
        results["steps"]["1_list_page_goto"] = {
            "status": "OK" if offers_bs and not is_cf_list else ("CF_BLOCK" if is_cf_list else "EMPTY"),
            "offers_count": len(offers_bs),
            "final_url": page.url,
            "cloudflare": is_cf_list,
            "nav_attempts": nav_attempts,
            "cf_seen_on_attempts": nav_cf_seen,
            "method": "page.goto + wait 3s (+ oczekiwanie na auto-rozwiązanie CF) + BeautifulSoup(article.job)",
            "time_s": round(time.time() - t1, 1),
        }
        log(f"  [OK] page.goto: {len(offers_bs)} ofert (CF: {is_cf_list}, próby: {nav_attempts})")

        # ═══════════════ KROK 2 (L4): evaluate+fetch na LIŚCIE ═══════════════
        log("\n[KROK 2 (L4)] evaluate+fetch na URL listy PO zakończeniu nawigacji...")
        t2 = time.time()
        list_path = USEME_LIST_URL.replace(USEME_BASE, "")
        raw_list_html = fetch_via_evaluate(page, list_path)
        l4_status = "FAIL"
        l4_offers = []
        l4_cf = None
        if raw_list_html:
            with open(LIST_HTML_RAW, "w", encoding="utf-8") as f:
                f.write(raw_list_html)
            l4_cf = is_cloudflare(raw_list_html)
            if not l4_cf:
                l4_offers = parse_offers_from_html(raw_list_html)
                l4_status = "OK" if l4_offers else "PARSE_EMPTY"
            else:
                l4_status = "CF_BLOCK"
        results["steps"]["2_list_evaluate_fetch"] = {
            "status": l4_status,
            "offers_count": len(l4_offers),
            "cloudflare": l4_cf,
            "raw_html_size": len(raw_list_html) if raw_list_html else 0,
            "time_s": round(time.time() - t2, 1),
        }
        same_as_goto = (len(l4_offers) > 0 and [o.get("url") for o in l4_offers] == [o.get("url") for o in offers_bs])
        results["steps"]["2_list_evaluate_fetch"]["same_as_page_goto"] = same_as_goto
        log(f"  [L4] evaluate+fetch: status={l4_status}, ofert={len(l4_offers)}, identyczne z goto: {same_as_goto}")

        # Wybór listy bazowej (preferujemy page.goto – metoda pewna)
        offers = offers_bs if offers_bs else l4_offers
        if not offers:
            log("[FATAL] zero ofert z obu metod")
            results["status"] = "FAIL"
            results["cf_blocked"] = is_cf_list
            _save(results, attempt=headless)
            return 1, is_cf_list  # jeśli CF – sygnał do retry w trybie widocznym

        # ═══════════════ KROK 3: MARKER ═══════════════
        log("\n[KROK 3] Marker last_offer.txt (URL ostatniej oferty)...")
        t3 = time.time()
        new_offers, marker_info = check_marker_and_new(offers)
        results["steps"]["3_marker"] = dict(marker_info)
        results["steps"]["3_marker"]["time_s"] = round(time.time() - t3, 1)
        results["steps"]["3_marker"]["first_offer_title"] = offers[0].get("title", "?")[:80]
        log(f"  [MARKER] nowych ofert: {len(new_offers)}")

        # W flow bierzemy NOWE oferty do selekcji (zgodnie z mechanizmem)
        offers_for_ai = new_offers if new_offers else offers

        # ═══════════════ KROK 4: AI #1 – SELEKCJA ═══════════════
        log("\n[KROK 4] AI #1 – selekcja 2-3 najwartościowszych ofert (DeepSeek)...")
        t4 = time.time()
        ai_selection = ai_select_offers(offers_for_ai)
        ai_selection["used_offers_count"] = len(offers_for_ai)
        results["steps"]["4_ai_selection"] = {
            "status": "FALLBACK" if ai_selection.get("fallback") else "OK",
            "selected_count": len(ai_selection.get("selected", [])),
            "rejected_count": len(ai_selection.get("rejected", [])),
            "time_s": round(time.time() - t4, 1),
        }

        # Wybrane indeksy -> detale
        selected = []
        for s in ai_selection.get("selected", []):
            idx = s.get("index", -1)
            if 0 <= idx < len(offers_for_ai):
                selected.append((idx, offers_for_ai[idx], s.get("reason", "")))
            if len(selected) >= MAX_DETAIL_OFFERS:
                break

        # ═══════════════ KROK 5: DETALE (evaluate+fetch + parser v3) ═══════════════
        log("\n[KROK 5] Detale: evaluate+fetch -> surowy HTML -> parser JSON-LD+CSS...")
        t5 = time.time()
        details = []
        for n, (idx, offer, reason) in enumerate(selected, 1):
            url = offer.get("url", "")
            log(f"  [{n}/{len(selected)}] {offer.get('title','?')[:70]}...")
            url_path = url.replace(USEME_BASE, "") if url.startswith(USEME_BASE) else url
            html_raw = fetch_via_evaluate(page, url_path)
            detail_parsed = parse_offer_detail_v3(html_raw, url)
            method = "evaluate+fetch"
            fallback_note = ""

            if detail_parsed.get("status") in ("cloudflare", "empty"):
                # FALLBACK: page.goto + renderowany HTML
                raw_status = detail_parsed.get("status")
                log(f"    [WARN] surowy HTML = {raw_status}. Fallback: page.goto + page.content()...")
                try:
                    html_rendered = navigate_and_wait(page, url)
                    detail_parsed = parse_offer_detail_v3(html_rendered, url)
                    method = "page.goto_rendered (fallback)"
                    fallback_note = f"raw_fetch={raw_status}"
                except Exception as e:
                    detail_parsed = {"status": "fetch_failed", "error": str(e), "source_url": url}

            entry = {
                "index": idx,
                "offer": offer,
                "selection_reason": reason,
                "fetch_method": method,
                "fallback_note": fallback_note,
                "raw_html_size": len(html_raw) if html_raw else 0,
                "detail_parsed": detail_parsed,
            }
            details.append(entry)

            # Zapis surowego HTML + sparsowanego JSON
            base = os.path.join(DETAILS_DIR, f"detail_{idx}")
            with open(base + ".html", "w", encoding="utf-8") as f:
                f.write(html_raw or "")
            with open(base + ".json", "w", encoding="utf-8") as f:
                json.dump(entry, f, ensure_ascii=False, indent=2)

            status = detail_parsed.get("status")
            log(f"    status={status}, komplet: {detail_parsed.get('complete')}, tytuł: {str(detail_parsed.get('title',''))[:50]}")
            time.sleep(1.0)  # rate limiting

        ok_details = [d for d in details if d["detail_parsed"].get("status") == "ok"]
        complete_details = [d for d in ok_details if d["detail_parsed"].get("complete")]
        results["steps"]["5_details"] = {
            "status": "OK" if ok_details else "FAIL",
            "total": len(details),
            "parsed_ok": len(ok_details),
            "complete": len(complete_details),
            "time_s": round(time.time() - t5, 1),
        }
        log(f"  [OK] detale sparsowane: {len(ok_details)}/{len(details)}, kompletne: {len(complete_details)}")

        # ═══════════════ KROK 6: AI #2 – PROPOZYCJE (POJEDYNCZO) ═══════════════
        log("\n[KROK 6] AI #2 – propozycje POJEDYNCZO dla każdej oferty...")
        t6 = time.time()
        proposals = []
        for i, d in enumerate(details):
            parsed = d.get("detail_parsed", {})
            if parsed.get("status") != "ok":
                proposals.append({
                    "index": d.get("index"),
                    "title": d["offer"].get("title", "?"),
                    "proposal": {"proposal_text": "[SKIP] brak danych detalu", "proposed_rate": None, "key_points": []},
                    "error": f"detail_status={parsed.get('status')}",
                })
                continue
            prop = ai_generate_proposal(d["offer"], parsed, i + 1, len(details))
            proposals.append(prop)

        ai2_ok = [p for p in proposals if "error" not in p and p.get("proposal", {}).get("proposal_text") and "[ERROR]" not in p["proposal"]["proposal_text"]]
        results["steps"]["6_ai_proposals"] = {
            "status": "OK" if ai2_ok else "FAIL",
            "generated": len(ai2_ok),
            "total": len(proposals),
            "per_offer_calls": True,
            "time_s": round(time.time() - t6, 1),
        }
        log(f"  [OK] propozycje: {len(ai2_ok)}/{len(proposals)}")

        # ═══════════════ KROK 7: ZAPIS WYNIKÓW ═══════════════
        log("\n[KROK 7] Zapis final_flow_results.json...")
        results["offers_from_list"] = offers
        results["new_offers_after_marker"] = offers_for_ai
        results["list_comparison"] = {
            "page_goto_offers": len(offers_bs),
            "evaluate_fetch_offers": len(l4_offers),
            "evaluate_fetch_status": l4_status,
            "identical": same_as_goto,
            "note": "L4: evaluate+fetch na liście PO zakończeniu nawigacji"
        }
        results["ai_selection"] = ai_selection
        results["details"] = details
        results["proposals"] = proposals
        results["timestamp_end"] = timestamp()
        results["total_time_s"] = elapsed()
        results["status"] = "OK"
        results["sent_anything"] = False

        _save(results, attempt=headless)
        _print_summary(results)
        return 0, False

    except Exception as e:
        import traceback
        traceback.print_exc()
        results["status"] = "FAIL"
        results["error"] = str(e)
        results["total_time_s"] = elapsed()
        _save(results, attempt=headless)
        return 1, False

    finally:
        if browser:
            browser.close()
        if playwright:
            playwright.stop()
        log("[INFO] Playwright zamknięty")


def main():
    """Uruchamia flow: najpierw headless=True (stack z testu 12); jeśli Cloudflare
    blokuje headless – automatyczny fallback na headless=False (widoczna przeglądarka)."""
    for headless in (True, False):
        code, cf_blocked = run_attempt(headless)
        if not cf_blocked:
            return code
        log(f"[INFO] headless={headless} zablokowany przez Cloudflare – ponawiam z headless={not headless}")


def _save(results, attempt=None):
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def _print_summary(r):
    print("\n" + "=" * 72)
    print("  PODSUMOWANIE TESTU 15 (FINAL FLOW v3, DRY RUN)")
    print("=" * 72)
    steps = r.get("steps", {})
    s = lambda k: steps.get(k, {}).get("status", "?")
    print(f"  0. Init:                {'✅' if s('0_init')=='OK' else '❌'}")
    s1 = steps.get("1_list_page_goto", {})
    print(f"  1. Lista (page.goto):   {'✅' if s1.get('status')=='OK' else '❌'} ({s1.get('offers_count',0)} ofert, CF: {s1.get('cloudflare')})")
    s2 = steps.get("2_list_evaluate_fetch", {})
    print(f"  2. L4 evaluate+fetch:   {'✅' if s2.get('status')=='OK' else '⚠️' if s2.get('status') in ('CF_BLOCK','FAIL') else '❌'} ({s2.get('offers_count',0)} ofert, status: {s2.get('status')})")
    s3 = steps.get("3_marker", {})
    print(f"  3. Marker:              {'✅' if s3.get('status') in ('first_run','found','no_new','not_found_all_new') else '❌'} ({s3.get('status')}, nowych: {s3.get('new_count')})")
    s4 = steps.get("4_ai_selection", {})
    print(f"  4. AI #1 selekcja:      {'✅' if s4.get('status')=='OK' else '⚠️ FALLBACK'} ({s4.get('selected_count',0)} wybranych)")
    s5 = steps.get("5_details", {})
    print(f"  5. Detale (eval+fetch): {'✅' if s5.get('status')=='OK' else '❌'} ({s5.get('complete',0)}/{s5.get('total',0)} kompletne)")
    s6 = steps.get("6_ai_proposals", {})
    print(f"  6. AI #2 propozycje:    {'✅' if s6.get('status')=='OK' else '⚠️'} ({s6.get('generated',0)}/{s6.get('total',0)})")
    print(f"\n  CZAS CAŁKOWITY: {r.get('total_time_s','?')} s")
    print(f"  WYSŁANO COKOLWIEK: {'NIE ✅' if r.get('sent_anything') is False else '???'}")
    for d in r.get("details", []):
        p = d.get("detail_parsed", {})
        print(f"  - [{d.get('index')}] {str(p.get('title','?'))[:60]} | status={p.get('status')} | komplet={p.get('complete')} | metoda={d.get('fetch_method')}")
    for p in r.get("proposals", []):
        t = p.get("proposal", {}).get("proposal_text", "")
        print(f"\n  >>> {p.get('title','?')[:60]}")
        print(f"      {t[:220]}")
    print("\n" + "=" * 72)


if __name__ == "__main__":
    sys.exit(main())
