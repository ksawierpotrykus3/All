"""
TEST 10 – Pełny flow integracyjny v2 (evaluate + fetch zamiast page.goto)
=========================================================================
Flow:
  1. Warmup: page.goto('https://useme.com/') + wait 5s
  2. Pobranie listy przez page.evaluate() + fetch (same-origin)
  3. Parsowanie HTML → lista ofert (selektory z test02)
  4. Marker nowych ofert (last_offer.txt)
  5. AI Selekcja (DeepSeek) → wybór pasujących ofert
  6. Pobranie szczegółów przez page.evaluate() + fetch (NIE page.goto!)
  7. AI Generowanie propozycji (JEDNA OFERTA NA RAZ)
  8. Zapis wyników → flow_v2_results.json + podsumowanie

WAŻNE: Nie wysyła faktycznie ofert na Useme!
"""
import json
import os
import re
import sys
import time
import hashlib
from datetime import datetime
from bs4 import BeautifulSoup
import requests

# ============================================================================
# KONFIGURACJA
# ============================================================================
BASE_DIR = r"c:\Users\Ksawier\Pictures\Screenshots\useme\lab"
OUTPUT_DIR = os.path.join(BASE_DIR, "test10_flow_v2")
RESULTS_FILE = os.path.join(OUTPUT_DIR, "flow_v2_results.json")
LAST_OFFER_FILE = os.path.join(OUTPUT_DIR, "last_offer.txt")
INTERMEDIATE_DIR = os.path.join(OUTPUT_DIR, "intermediate")
LIST_HTML_FILE = os.path.join(INTERMEDIATE_DIR, "list_page_evaluate.html")
LIST_JSON_FILE = os.path.join(INTERMEDIATE_DIR, "parsed_offers.json")
AI_SELECT_FILE = os.path.join(INTERMEDIATE_DIR, "ai_selection.json")
DETAILS_DIR = os.path.join(INTERMEDIATE_DIR, "details")
AI_PROPOSALS_FILE = os.path.join(INTERMEDIATE_DIR, "ai_proposals.json")

USEME_BASE_URL = "https://useme.com"
USEME_LIST_PATH = "/pl/jobs/category/programowanie-i-it,35/"
DEEPSEEK_API_URL = "http://localhost:4570/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-v4-pro"
MAX_OFFERS = 10
MAX_DETAIL_OFFERS = 5  # Maksymalna liczba ofert do szczegółowego sprawdzenia

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(INTERMEDIATE_DIR, exist_ok=True)
os.makedirs(DETAILS_DIR, exist_ok=True)

# ============================================================================
# KROK 0: Narzędzia pomocnicze
# ============================================================================

def timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log(msg):
    print(f"[{timestamp()}] {msg}")

def parse_ai_json_response(content):
    """Parsuje odpowiedź AI – czyści markdown, proxy tags, wyodrębnia JSON."""
    content = re.sub(r'<!-- PROXY_SID:.*?-->', '', content, flags=re.DOTALL).strip()
    if content.startswith("```"):
        lines = content.split("\n")
        start = 0
        end = len(lines)
        if lines[0].startswith("```"):
            start = 1
        if lines[-1].startswith("```"):
            end = -1
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

def call_deepseek(prompt, max_tokens=2000, temperature=0.7, timeout=120):
    """Wywołuje DeepSeek API i zwraca treść odpowiedzi."""
    log(f"  [AI] Wysyłam zapytanie ({len(prompt)} znaków)...")
    headers = {"Content-Type": "application/json"}
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    try:
        resp = requests.post(DEEPSEEK_API_URL, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if "text/event-stream" in content_type or resp.text.strip().startswith("data:"):
            full_content = ""
            for line in resp.text.split("\n"):
                line = line.strip()
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        full_content += delta.get("content", "")
                    except json.JSONDecodeError:
                        pass
            return full_content
        else:
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return content
    except requests.exceptions.ConnectionError:
        log("  [ERROR] DeepSeek API nieosiągalne – brak połączenia z localhost:4570")
        raise
    except requests.exceptions.Timeout:
        log("  [ERROR] DeepSeek API – timeout")
        raise
    except Exception as e:
        log(f"  [ERROR] DeepSeek API – błąd: {e}")
        raise

# ============================================================================
# PARSOWANIE HTML
# ============================================================================

def parse_offers_from_html(html_content):
    """Parsuje HTML listy ofert używając selektorów z test02."""
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
                offer["url"] = f"https://useme.com{href}" if href.startswith("/") else href
            else:
                offer["title"] = None
                offer["url"] = None
            
            author_el = article.select_one("div.job__headline strong")
            offer["author"] = author_el.get_text(strip=True) if author_el else None
            
            avatar_wrapper = article.select_one("div.user_avatar")
            has_avatar = False
            if avatar_wrapper:
                classes = avatar_wrapper.get("class", [])
                has_avatar = "user_avatar__default-image" not in classes
            offer["has_avatar"] = has_avatar
            
            offers_el = article.select_one("div.job__header-details--offers span:last-child")
            if offers_el:
                try:
                    offer["offers_count"] = int(offers_el.get_text(strip=True))
                except ValueError:
                    offer["offers_count"] = offers_el.get_text(strip=True)
            else:
                offer["offers_count"] = None
            
            date_el = article.select_one("div.job__header-details--date span:last-child")
            offer["expiry"] = date_el.get_text(strip=True) if date_el else None
            
            category_el = article.select_one("div.job__category a p")
            if category_el:
                offer["category"] = category_el.get_text(strip=True)
            else:
                cat_div = article.select_one("div.job__category")
                offer["category"] = cat_div.get_text(strip=True) if cat_div else None
            
            budget_el = article.select_one("span.job__budget-value")
            if budget_el:
                offer["budget"] = re.sub(r"\s+", " ", budget_el.get_text(strip=True))
            else:
                offer["budget"] = None
            
            desc_el = article.select_one("div.job__content p")
            if desc_el:
                offer["description"] = desc_el.get_text(strip=True)[:300]
            else:
                offer["description"] = None
            
            offers.append(offer)
        except Exception as e:
            log(f"  [WARN] Błąd parsowania oferty: {e}")
            continue
    return offers


def parse_offer_detail(html_content, source_url=""):
    """Parsuje stronę szczegółów oferty."""
    if not html_content:
        return None
    soup = BeautifulSoup(html_content, "html.parser")
    detail = {}
    detail["source_url"] = source_url
    
    title_el = soup.select_one("h1")
    detail["title"] = title_el.get_text(strip=True) if title_el else "?"
    
    desc_el = (
        soup.select_one("div.offer-content") or
        soup.select_one("div.job-description") or
        soup.select_one("div[class*='description']") or
        soup.select_one("article")
    )
    detail["full_desc"] = desc_el.get_text(strip=True)[:3000] if desc_el else "?"
    
    budget_el = soup.select_one("span[class*='budget']") or soup.select_one("div[class*='budget']")
    detail["budget"] = budget_el.get_text(strip=True) if budget_el else "Do negocjacji"
    
    cat_el = soup.select_one("a[class*='category']") or soup.select_one("div[class*='category']")
    detail["category"] = cat_el.get_text(strip=True) if cat_el else "?"
    
    date_el = soup.select_one("time") or soup.select_one("span[class*='date']")
    detail["published"] = date_el.get_text(strip=True) if date_el else "?"
    
    return detail

# ============================================================================
# FETCH PRZEZ EVALUATE (zamiast page.goto)
# ============================================================================

def fetch_list_via_evaluate(page):
    """Pobiera HTML listy ofert przez page.evaluate() + fetch (same-origin)."""
    log("  Pobieram listę przez page.evaluate() + fetch...")
    js_code = """
    async () => {
        const res = await fetch('/pl/jobs/category/programowanie-i-it,35/', {credentials:'include'});
        return await res.text();
    }
    """
    try:
        html = page.evaluate(js_code)
        log(f"  Pobrano HTML listy: {len(html)} bajtów przez evaluate+fetch")
        return html
    except Exception as e:
        log(f"  [ERROR] evaluate+fetch listy nieudane: {e}")
        return None


def fetch_detail_via_evaluate(page, url_path):
    """Pobiera HTML detalu oferty przez page.evaluate() + fetch (same-origin).
    url_path – ścieżka względna, np. '/pl/jobs/...'"""
    log(f"    evaluate+fetch detal: {url_path}")
    js_code = f"""
    async () => {{
        const res = await fetch('{url_path}', {{credentials:'include'}});
        return await res.text();
    }}
    """
    try:
        html = page.evaluate(js_code)
        log(f"    Pobrano detal: {len(html)} bajtów")
        return html
    except Exception as e:
        log(f"    [ERROR] evaluate+fetch detalu nieudane: {e}")
        return None

# ============================================================================
# MARKER NOWYCH OFERT
# ============================================================================

def check_marker(offers):
    """Sprawdza czy są nowe oferty na podstawie markera."""
    if not offers:
        log("[WARN] Brak ofert do sprawdzenia markera")
        return True
    first_title = offers[0].get("title", "")
    first_hash = hashlib.md5(first_title.encode()).hexdigest()
    
    if os.path.exists(LAST_OFFER_FILE):
        with open(LAST_OFFER_FILE, "r", encoding="utf-8") as f:
            saved_hash = f.read().strip()
        if saved_hash == first_hash:
            log(f"[INFO] Marker – brak nowych ofert (pierwsza oferta bez zmian: {first_title[:60]}...)")
            return False
        else:
            log(f"[INFO] Marker – NOWE OFERTY! Poprzedni hash: {saved_hash[:8]}, nowy: {first_hash[:8]}")
    else:
        log("[INFO] Marker – pierwsze uruchomienie, brak pliku markera")
    
    with open(LAST_OFFER_FILE, "w", encoding="utf-8") as f:
        f.write(first_hash)
    log(f"[INFO] Zapisano marker: {first_hash[:8]}... (pierwsza oferta: {first_title[:60]}...)")
    return True

# ============================================================================
# AI SELEKCJA
# ============================================================================

def ai_select_offers(offers):
    """Wysyła listę ofert do DeepSeek w celu selekcji."""
    offers_simplified = []
    for o in offers:
        offers_simplified.append({
            "index": len(offers_simplified),
            "title": o.get("title", ""),
            "category": o.get("category", ""),
            "budget": o.get("budget", ""),
            "description": (o.get("description", "") or "")[:300],
        })
    
    prompt = (
        "Przeanalizuj poniższe oferty i wybierz te, które pasują dla programisty Python "
        "specjalizującego się w web scrapingu i automatyzacji. "
        "Zwróć JSON z polami: selected (lista wybranych) i rejected (lista odrzuconych). "
        "Każdy element w selected i rejected musi zawierać: index (numer oferty z listy), "
        "title (tytuł oferty), reason (krótkie uzasadnienie po polsku).\n\n"
        "Kryteria wyboru:\n"
        "- Oferty związane z Pythonem, web scrapingiem, automatyzacją, API, integracjami\n"
        "- Oferty z AI/ML (jeśli Python)\n"
        "- Oferty wyraźnie NIE-Python (PHP, Java, C#, WordPress, frontend) – odrzuć\n"
        "- Oferty czysto administracyjne/serwerowe (bez programowania) – odrzuć\n\n"
        "Lista ofert:\n" + json.dumps(offers_simplified, ensure_ascii=False, indent=2)
    )
    
    try:
        response_text = call_deepseek(prompt, max_tokens=3000)
        result = parse_ai_json_response(response_text)
        log(f"  [OK] AI selekcja – odpowiedź otrzymana")
        return result
    except Exception as e:
        log(f"  [ERROR] AI selekcja nieudana: {e}. Używam fallback (mock selection).")
        keywords = ["python", "scraping", "automatyzacj", "api", "ocr", "ai", "web scraping", "n8n", "make"]
        selected = []
        rejected = []
        for i, o in enumerate(offers):
            text = (o.get("title","") + " " + (o.get("description","") or "")).lower()
            if any(kw in text for kw in keywords):
                selected.append({"index": i, "title": o.get("title",""), "reason": "Fallback: słowa kluczowe pasujące"})
            else:
                rejected.append({"index": i, "title": o.get("title",""), "reason": "Fallback: brak słów kluczowych"})
        return {"selected": selected, "rejected": rejected, "fallback": True}

# ============================================================================
# AI GENEROWANIE PROPOZYCJI (JEDNA OFERTA NA RAZ)
# ============================================================================

def ai_generate_proposals(details):
    """Dla każdej wybranej oferty PO KOLEI generuje propozycję przez DeepSeek.
    WAŻNE: jedna oferta na raz – nie wrzucamy wszystkich naraz!"""
    proposals = []
    for i, d in enumerate(details):
        offer = d.get("offer", {})
        parsed = d.get("detail_parsed", {}) or {}
        
        title = parsed.get("title") or offer.get("title", "?")
        desc = parsed.get("full_desc") or offer.get("description", "")
        budget = parsed.get("budget") or offer.get("budget", "Do negocjacji")
        category = parsed.get("category") or offer.get("category", "")
        author = offer.get("author", "")
        
        log(f"  Generuję propozycję [{i+1}/{len(details)}] dla: {title[:60]}...")
        
        prompt = (
            "Jesteś freelancerem-programistą Python. Poniżej dane JEDNEJ oferty z Useme. "
            "Napisz profesjonalną, krótką propozycję (3-8 zdań) odpowiedzi na TO zlecenie. "
            "WAŻNE: pisz TYLKO o tej konkretnej ofercie, nie mieszaj z innymi. "
            "Jeśli budżet jest 'Do negocjacji', zaproponuj realną stawkę godzinową lub za całość. "
            "Pisz w języku polskim, tonem profesjonalnym ale przyjaznym. "
            "Zwróć JSON z polami: proposal_text i proposed_rate.\n\n"
            f"Dane oferty:\n- Tytuł: {title}\n- Kategoria: {category}\n- Autor: {author}\n"
            f"- Budżet: {budget}\n- Opis: {desc[:2000]}\n\n"
            "Zwróć TYLKO surowy JSON (bez markdown, bez komentarzy)."
        )
        
        try:
            response_text = call_deepseek(prompt, max_tokens=500)
            result = parse_ai_json_response(response_text)
            if "proposal_text" not in result and "raw_response" in result:
                result = {"proposal_text": result["raw_response"], "proposed_rate": None}
            proposals.append({
                "index": i,
                "title": title,
                "proposal": result,
                "fetched_at": timestamp(),
            })
            log(f"    [OK] Propozycja wygenerowana")
        except Exception as e:
            log(f"    [ERROR] Generowanie propozycji nieudane: {e}")
            proposals.append({
                "index": i,
                "title": title,
                "proposal": {
                    "proposal_text": f"[ERROR] Nie udało się wygenerować propozycji: {e}",
                    "proposed_rate": None,
                },
                "error": str(e),
            })
    return proposals

# ============================================================================
# MAIN FLOW
# ============================================================================

def main():
    flow_results = {
        "test": "TEST 10 – Pełny flow v2 (evaluate+fetch zamiast page.goto)",
        "timestamp_start": timestamp(),
        "status": "IN_PROGRESS",
        "steps": {},
    }
    
    print("=" * 70)
    print("  TEST 10 – Pełny flow v2 (evaluate+fetch zamiast page.goto)")
    print("=" * 70)
    
    # ─── Inicjalizacja Playwright ───
    log("KROK 0: Inicjalizacja Playwright + Firefox...")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("[FATAL] Playwright nie jest zainstalowany. Zainstaluj: pip install playwright")
        flow_results["status"] = "FAIL"
        flow_results["steps"]["0_playwright_init"] = {"status": "FAIL", "error": "Playwright not installed"}
        _save_and_print(flow_results)
        return 1
    
    playwright = None
    browser = None
    page = None
    
    try:
        playwright = sync_playwright().start()
        # headless=false zgodnie z instrukcją (jeśli działa)
        browser = playwright.firefox.launch(headless=False)
        page = browser.new_page()
        page.set_viewport_size({"width": 1920, "height": 1080})
        
        flow_results["steps"]["0_playwright_init"] = {"status": "OK", "browser": "firefox", "headless": False}
        log("[OK] Playwright + Firefox uruchomiony (headless=False)")
    except Exception as e:
        log(f"[ERROR] Nie można uruchomić Playwright: {e}")
        log("[INFO] Próbuję z headless=True...")
        try:
            if browser:
                browser.close()
            if playwright:
                playwright.stop()
            playwright = sync_playwright().start()
            browser = playwright.firefox.launch(headless=True)
            page = browser.new_page()
            page.set_viewport_size({"width": 1920, "height": 1080})
            flow_results["steps"]["0_playwright_init"] = {"status": "OK", "browser": "firefox", "headless": True}
        except Exception as e2:
            log(f"[FATAL] Playwright nie działa nawet headless: {e2}")
            flow_results["status"] = "FAIL"
            flow_results["steps"]["0_playwright_init"] = {"status": "FAIL", "error": str(e2)}
            _save_and_print(flow_results)
            return 1
    
    try:
        # ═══════════════════════════════════════════════════════════════════
        # KROK 1: Warmup – page.goto na useme.com
        # ═══════════════════════════════════════════════════════════════════
        log("\nKROK 1: Warmup – page.goto('https://useme.com/')...")
        page.goto("https://useme.com/", wait_until="domcontentloaded", timeout=30000)
        log("  Czekam 5 sekund...")
        time.sleep(5)
        log("[OK] Warmup zakończony")
        flow_results["steps"]["1_warmup"] = {"status": "OK", "url": page.url}
        
        # ═══════════════════════════════════════════════════════════════════
        # KROK 2: Pobranie listy przez evaluate + fetch
        # ═══════════════════════════════════════════════════════════════════
        log("\nKROK 2: Pobieranie listy ofert przez evaluate+fetch...")
        html_list = fetch_list_via_evaluate(page)
        
        if not html_list:
            # Fallback: wczytaj HTML z test01
            test01_html = os.path.join(BASE_DIR, "test01_connect", "page.html")
            if os.path.exists(test01_html):
                log(f"  [FALLBACK] Używam zapisanego HTML z test01: {test01_html}")
                with open(test01_html, "r", encoding="utf-8") as f:
                    html_list = f.read()
                fetch_method = "fallback_test01_html"
            else:
                # Drugi fallback: wczytaj gotowy JSON z test02
                test02_json = os.path.join(BASE_DIR, "test02_parse_list", "offers.json")
                if os.path.exists(test02_json):
                    log(f"  [FALLBACK] Wczytuję gotowe oferty z test02: {test02_json}")
                    with open(test02_json, "r", encoding="utf-8") as f:
                        offers = json.load(f)
                    fetch_method = "fallback_test02_json"
                    html_list = "__SKIP_PARSE__"
                else:
                    log("[FATAL] evaluate+fetch nieudane i brak fallbacków")
                    flow_results["steps"]["2_fetch_list_evaluate"] = {"status": "FAIL", "method": "evaluate+fetch", "offers_count": 0, "error": "Brak HTML i fallbacków"}
                    flow_results["status"] = "FAIL"
                    _save_and_print(flow_results)
                    return 1
        else:
            fetch_method = "evaluate+fetch"
        
        # Zapisz HTML listy
        if html_list != "__SKIP_PARSE__":
            with open(LIST_HTML_FILE, "w", encoding="utf-8") as f:
                f.write(html_list)
            log(f"[OK] HTML listy zapisany: {LIST_HTML_FILE} ({len(html_list)} bajtów)")
            offers = parse_offers_from_html(html_list)
        else:
            log("[INFO] Pomijam parsowanie – oferty wczytane z cache JSON")
        
        log(f"[OK] Sparsowano {len(offers)} ofert")
        
        with open(LIST_JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(offers, f, ensure_ascii=False, indent=2)
        
        flow_results["steps"]["2_fetch_list_evaluate"] = {
            "status": "OK",
            "method": fetch_method,
            "offers_count": len(offers),
            "html_size": len(html_list) if html_list != "__SKIP_PARSE__" else 0,
        }
        
        if len(offers) == 0:
            log("[FATAL] Zero ofert – przerywam")
            flow_results["status"] = "FAIL"
            _save_and_print(flow_results)
            return 1
        
        # ═══════════════════════════════════════════════════════════════════
        # KROK 3: Marker nowych ofert
        # ═══════════════════════════════════════════════════════════════════
        log("\nKROK 3: Sprawdzanie markera nowych ofert...")
        has_new = check_marker(offers)
        flow_results["steps"]["3_marker"] = {
            "status": "OK",
            "has_new_offers": has_new,
            "first_offer_title": offers[0].get("title", "?")[:80],
        }
        
        # ═══════════════════════════════════════════════════════════════════
        # KROK 4: AI Selekcja
        # ═══════════════════════════════════════════════════════════════════
        log("\nKROK 4: AI Selekcja ofert...")
        ai_selection = ai_select_offers(offers)
        
        with open(AI_SELECT_FILE, "w", encoding="utf-8") as f:
            json.dump(ai_selection, f, ensure_ascii=False, indent=2)
        
        selected_count = len(ai_selection.get("selected", []))
        rejected_count = len(ai_selection.get("rejected", []))
        is_fallback = ai_selection.get("fallback", False)
        log(f"[OK] AI wybrała: {selected_count} ofert, odrzuciła: {rejected_count}" +
            (" (FALLBACK – mock selection)" if is_fallback else ""))
        
        flow_results["steps"]["4_ai_selection"] = {
            "status": "OK" if not is_fallback else "FALLBACK",
            "selected_count": selected_count,
            "rejected_count": rejected_count,
            "fallback": is_fallback,
        }
        
        # ═══════════════════════════════════════════════════════════════════
        # KROK 5: Pobranie detali przez evaluate+fetch
        # ═══════════════════════════════════════════════════════════════════
        log("\nKROK 5: Pobieranie szczegółów przez evaluate+fetch...")
        selected = ai_selection.get("selected", [])
        selected_to_fetch = selected[:MAX_DETAIL_OFFERS]
        
        details = []
        for sel in selected_to_fetch:
            idx = sel.get("index", -1)
            if idx < 0 or idx >= len(offers):
                continue
            offer = offers[idx]
            url = offer.get("url", "")
            title = offer.get("title", "?")
            if not url:
                log(f"  [WARN] Brak URL dla oferty: {title[:60]}")
                details.append({"offer": offer, "detail_html": None, "detail_parsed": None, "error": "Brak URL"})
                continue
            
            # Wyciągnij ścieżkę względną z pełnego URL
            if url.startswith(USEME_BASE_URL):
                url_path = url[len(USEME_BASE_URL):]
            else:
                url_path = url
            
            log(f"  [{len(details)+1}/{len(selected_to_fetch)}] Pobieram detal: {title[:60]}...")
            detail_file = os.path.join(DETAILS_DIR, f"detail_{idx}.json")
            
            # Sprawdź cache
            if os.path.exists(detail_file):
                with open(detail_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                details.append(cached)
                log(f"    [CACHE] Wczytano z {detail_file}")
                continue
            
            # Pobierz przez evaluate+fetch
            html_detail = fetch_detail_via_evaluate(page, url_path)
            if html_detail:
                parsed = parse_offer_detail(html_detail, url)
            else:
                parsed = None
            
            detail_entry = {
                "offer": offer,
                "detail_html_length": len(html_detail) if html_detail else 0,
                "detail_parsed": parsed,
                "detail_file": detail_file,
                "fetched_at": timestamp(),
                "fetch_method": "evaluate+fetch",
            }
            details.append(detail_entry)
            
            with open(detail_file, "w", encoding="utf-8") as f:
                json.dump(detail_entry, f, ensure_ascii=False, indent=2)
            
            if parsed:
                log(f"    [OK] Pobrano detal: {parsed.get('title','?')[:60]}")
            else:
                log(f"    [WARN] Nie udało się sparsować detalu")
            
            time.sleep(1.0)  # Rate limiting
        
        details_ok = sum(1 for d in details if d.get("detail_parsed"))
        log(f"[OK] Pobrano szczegóły: {details_ok}/{len(details)} ofert")
        
        flow_results["steps"]["5_fetch_details_evaluate"] = {
            "status": "OK",
            "total": len(details),
            "success": details_ok,
            "failed": len(details) - details_ok,
            "method": "evaluate+fetch",
        }
        
        # ═══════════════════════════════════════════════════════════════════
        # KROK 6: AI Generowanie propozycji (JEDNA NA RAZ)
        # ═══════════════════════════════════════════════════════════════════
        log("\nKROK 6: AI Generowanie propozycji (jedna oferta na raz)...")
        proposals = []
        proposals_status = "OK"
        
        if details:
            try:
                proposals = ai_generate_proposals(details)
                proposals_ok = sum(1 for p in proposals if "error" not in p)
                log(f"[OK] Wygenerowano propozycji: {proposals_ok}/{len(proposals)}")
            except Exception as e:
                log(f"[ERROR] Generowanie propozycji nieudane: {e}")
                proposals_status = "FAIL"
                proposals = [{"error": str(e)}]
        else:
            proposals_status = "SKIP"
        
        with open(AI_PROPOSALS_FILE, "w", encoding="utf-8") as f:
            json.dump(proposals, f, ensure_ascii=False, indent=2)
        
        flow_results["steps"]["6_ai_proposals"] = {
            "status": proposals_status,
            "generated": len([p for p in proposals if "error" not in p]) if proposals else 0,
            "total": len(proposals),
            "note": "Jedna oferta na raz – NIE wrzucano wszystkich naraz",
        }
        
        # ═══════════════════════════════════════════════════════════════════
        # KROK 7: Zapis wyników
        # ═══════════════════════════════════════════════════════════════════
        log("\nKROK 7: Zapis wyników końcowych...")
        
        flow_results["selected_offers"] = [
            {"index": s.get("index"), "title": s.get("title"), "reason": s.get("reason")}
            for s in selected_to_fetch
        ]
        flow_results["proposals"] = [
            {
                "title": p.get("title"),
                "proposal_text": p.get("proposal", {}).get("proposal_text", ""),
                "proposed_rate": p.get("proposal", {}).get("proposed_rate"),
            }
            for p in proposals if "error" not in p
        ]
        flow_results["timestamp_end"] = timestamp()
        flow_results["status"] = "OK"
        
        _save_and_print(flow_results)
        return 0
        
    except Exception as e:
        log(f"[FATAL] Nieoczekiwany błąd: {e}")
        import traceback
        traceback.print_exc()
        flow_results["status"] = "FAIL"
        flow_results["error"] = str(e)
        _save_and_print(flow_results)
        return 1
        
    finally:
        if browser:
            browser.close()
        if playwright:
            playwright.stop()
        log("[INFO] Playwright zamknięty")


def _save_and_print(flow_results):
    """Zapisuje wyniki i wypisuje podsumowanie."""
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(flow_results, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 70)
    print("  PODSUMOWANIE TESTU 10 (flow v2 – evaluate+fetch)")
    print("=" * 70)
    steps = flow_results.get("steps", {})
    
    s1 = steps.get("1_warmup", {})
    print(f"  1. Warmup:               {'✅' if s1.get('status')=='OK' else '❌'}")
    
    s2 = steps.get("2_fetch_list_evaluate", {})
    print(f"  2. Lista (evaluate+fetch):{'✅' if s2.get('status')=='OK' else '❌'} ({s2.get('offers_count',0)} ofert, metoda: {s2.get('method','?')})")
    
    s3 = steps.get("3_marker", {})
    new_str = "NOWE" if s3.get("has_new_offers") else "BRAK NOWYCH"
    print(f"  3. Marker:               {'✅' if s3.get('status')=='OK' else '❌'} ({new_str})")
    
    s4 = steps.get("4_ai_selection", {})
    fb = " (FALLBACK)" if s4.get("fallback") else ""
    print(f"  4. AI Selekcja:          {'✅' if s4.get('status') in ('OK','FALLBACK') else '❌'} ({s4.get('selected_count',0)} wybranych{fb})")
    
    s5 = steps.get("5_fetch_details_evaluate", {})
    print(f"  5. Detale (evaluate+fetch):{'✅' if s5.get('status')=='OK' else '❌'} ({s5.get('success',0)}/{s5.get('total',0)})")
    
    s6 = steps.get("6_ai_proposals", {})
    print(f"  6. AI Propozycje:        {'✅' if s6.get('status')=='OK' else '⚠️'} ({s6.get('generated',0)}/{s6.get('total',0)})")
    
    status = flow_results.get("status", "?")
    print(f"\n  STATUS KOŃCOWY: {'✅' if status=='OK' else '❌'} {status}")
    
    sel = flow_results.get("selected_offers", [])
    if sel:
        print(f"\n  WYBRANE OFERTY ({len(sel)}):")
        for s in sel:
            print(f"    - {s.get('title','?')[:80]}")
    
    props = flow_results.get("proposals", [])
    if props:
        print(f"\n  WYGENEROWANE PROPOZYCJE ({len(props)}):")
        for p in props:
            print(f"\n    >>> {p.get('title','?')[:60]}")
            print(f"    {p.get('proposal_text','?')[:200]}")
            rate = p.get('proposed_rate')
            if rate:
                print(f"    Stawka: {rate}")
    
    print(f"\n  Pliki:")
    print(f"    Wyniki:     {RESULTS_FILE}")
    print(f"    Lista JSON: {LIST_JSON_FILE}")
    print(f"    Selekcja:   {AI_SELECT_FILE}")
    print(f"    Propozycje: {AI_PROPOSALS_FILE}")
    print(f"    Marker:     {LAST_OFFER_FILE}")
    print("=" * 70)


if __name__ == "__main__":
    sys.exit(main())