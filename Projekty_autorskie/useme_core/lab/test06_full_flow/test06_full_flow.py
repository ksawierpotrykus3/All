"""
TEST 06 – Pełny flow integracyjny Useme + AI
==============================================
Flow:
  1. Pobranie listy ofert z Useme (WebFetch lub Playwright+Firefox)
  2. Parsowanie HTML → lista ofert (selektory z test02)
  3. Marker nowych ofert (last_offer.txt)
  4. AI Selekcja (DeepSeek) → wybór pasujących ofert
  5. Pobranie szczegółów wybranych ofert (WebFetch)
  6. AI Generowanie propozycji (DeepSeek)
  7. Zapis wyników → full_flow_results.json + podsumowanie

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
OUTPUT_DIR = os.path.join(BASE_DIR, "test06_full_flow")
RESULTS_FILE = os.path.join(OUTPUT_DIR, "full_flow_results.json")
LAST_OFFER_FILE = os.path.join(OUTPUT_DIR, "last_offer.txt")
INTERMEDIATE_DIR = os.path.join(OUTPUT_DIR, "intermediate")
LIST_HTML_FILE = os.path.join(INTERMEDIATE_DIR, "list_page.html")
LIST_JSON_FILE = os.path.join(INTERMEDIATE_DIR, "parsed_offers.json")
AI_SELECT_FILE = os.path.join(INTERMEDIATE_DIR, "ai_selection.json")
DETAILS_DIR = os.path.join(INTERMEDIATE_DIR, "details")
AI_PROPOSALS_FILE = os.path.join(INTERMEDIATE_DIR, "ai_proposals.json")

USEME_LIST_URL = "https://useme.com/pl/jobs/category/programowanie-i-it,35/"
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
    # Usuń znaczniki proxy
    content = re.sub(r'<!-- PROXY_SID:.*?-->', '', content, flags=re.DOTALL).strip()
    # Usuń markdown code fences
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
        # Spróbuj wyodrębnić JSON z tekstu
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {"raw_response": content, "parse_error": str(e)}

def call_deepseek(prompt, max_tokens=2000, temperature=0.7, timeout=120):
    """Wywołuje DeepSeek API i zwraca sparsowaną odpowiedź JSON."""
    log(f"Wysyłam zapytanie do DeepSeek ({len(prompt)} znaków)...")
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
            # SSE parsing
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
        log("[ERROR] DeepSeek API nieosiągalne – brak połączenia z localhost:4570")
        raise
    except requests.exceptions.Timeout:
        log("[ERROR] DeepSeek API – timeout")
        raise
    except Exception as e:
        log(f"[ERROR] DeepSeek API – błąd: {e}")
        raise

def fetch_html_webfetch(url):
    """Próbuje pobrać HTML przez WebFetch (narzędzie zewnętrzne). 
    Zwraca HTML lub None."""
    # Ta funkcja jest placeholderem – właściwe pobieranie przez WebFetch
    # odbywa się z poziomu agenta. W skrypcie standalone nie możemy wywołać WebFetch.
    # Zamiast tego używamy Playwright jako głównej metody,
    # a funkcja istnieje dla dokumentacji flow.
    log("[INFO] WebFetch nie jest dostępny z poziomu Pythona – użyj Playwright")
    return None

# ============================================================================
# KROK 1: Parsowanie HTML listy ofert
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
            # Tytuł + link
            title_el = article.select_one("a.job__title-link")
            if title_el:
                offer["title"] = title_el.get_text(strip=True)
                href = title_el.get("href", "")
                offer["url"] = f"https://useme.com{href}" if href.startswith("/") else href
            else:
                offer["title"] = None
                offer["url"] = None
            # Autor
            author_el = article.select_one("div.job__headline strong")
            offer["author"] = author_el.get_text(strip=True) if author_el else None
            # Avatar
            avatar_wrapper = article.select_one("div.user_avatar")
            has_avatar = False
            if avatar_wrapper:
                classes = avatar_wrapper.get("class", [])
                has_avatar = "user_avatar__default-image" not in classes
            offer["has_avatar"] = has_avatar
            # Liczba ofert
            offers_el = article.select_one("div.job__header-details--offers span:last-child")
            if offers_el:
                try:
                    offer["offers_count"] = int(offers_el.get_text(strip=True))
                except ValueError:
                    offer["offers_count"] = offers_el.get_text(strip=True)
            else:
                offer["offers_count"] = None
            # Czas wygaśnięcia
            date_el = article.select_one("div.job__header-details--date span:last-child")
            offer["expiry"] = date_el.get_text(strip=True) if date_el else None
            # Kategoria
            category_el = article.select_one("div.job__category a p")
            if category_el:
                offer["category"] = category_el.get_text(strip=True)
            else:
                cat_div = article.select_one("div.job__category")
                offer["category"] = cat_div.get_text(strip=True) if cat_div else None
            # Budżet
            budget_el = article.select_one("span.job__budget-value")
            if budget_el:
                offer["budget"] = re.sub(r"\s+", " ", budget_el.get_text(strip=True))
            else:
                offer["budget"] = None
            # Opis
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


def fetch_offers_playwright():
    """Pobiera listę ofert przez Playwright + Firefox."""
    log("Uruchamiam Playwright + Firefox...")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("[ERROR] Playwright nie jest zainstalowany. Zainstaluj: pip install playwright")
        return None
    
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        page = browser.new_page()
        page.set_viewport_size({"width": 1920, "height": 1080})
        log(f"  Nawiguję do: {USEME_LIST_URL}")
        page.goto(USEME_LIST_URL, wait_until="networkidle", timeout=30000)
        # Poczekaj na załadowanie ofert
        try:
            page.wait_for_selector("article.job", timeout=15000)
        except:
            log("  [WARN] Timeout na article.job – pobieram to co jest")
        html = page.content()
        browser.close()
        log(f"  Pobrano HTML: {len(html)} bajtów")
        return html


def fetch_offer_detail_playwright(url):
    """Pobiera stronę szczegółów oferty przez Playwright."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
            html = page.content()
        except Exception as e:
            log(f"  [WARN] Playwright nie pobrał {url}: {e}")
            html = None
        browser.close()
        return html


def parse_offer_detail(html_content, source_url=""):
    """Parsuje stronę szczegółów oferty."""
    if not html_content:
        return None
    soup = BeautifulSoup(html_content, "html.parser")
    detail = {}
    detail["source_url"] = source_url
    
    # Tytuł
    title_el = soup.select_one("h1")
    detail["title"] = title_el.get_text(strip=True) if title_el else "?"
    # Pełny opis – różne selektory
    desc_el = (
        soup.select_one("div.offer-content") or
        soup.select_one("div.job-description") or
        soup.select_one("div[class*='description']") or
        soup.select_one("article")
    )
    detail["full_desc"] = desc_el.get_text(strip=True)[:3000] if desc_el else "?"
    # Budżet
    budget_el = soup.select_one("span[class*='budget']") or soup.select_one("div[class*='budget']")
    detail["budget"] = budget_el.get_text(strip=True) if budget_el else "Do negocjacji"
    # Kategoria
    cat_el = soup.select_one("a[class*='category']") or soup.select_one("div[class*='category']")
    detail["category"] = cat_el.get_text(strip=True) if cat_el else "?"
    # Data publikacji
    date_el = soup.select_one("time") or soup.select_one("span[class*='date']")
    detail["published"] = date_el.get_text(strip=True) if date_el else "?"
    return detail

# ============================================================================
# KROK 2: Marker nowych ofert
# ============================================================================

def check_marker(offers):
    """Sprawdza czy są nowe oferty na podstawie markera (pierwszy tytuł)."""
    if not offers:
        log("[WARN] Brak ofert do sprawdzenia markera")
        return True  # Zakładamy, że są nowe
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
    
    # Zapisz nowy marker
    with open(LAST_OFFER_FILE, "w", encoding="utf-8") as f:
        f.write(first_hash)
    log(f"[INFO] Zapisano marker: {first_hash[:8]}... (pierwsza oferta: {first_title[:60]}...)")
    return True

# ============================================================================
# KROK 3: AI Selekcja ofert
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
        log(f"[OK] AI selekcja – odpowiedź otrzymana")
        return result
    except Exception as e:
        log(f"[ERROR] AI selekcja nieudana: {e}. Używam fallback.")
        # Fallback: wybierz oferty ze słowami kluczowymi Python/scraping/automatyzacja/API
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
# KROK 4: Pobieranie szczegółów
# ============================================================================

def fetch_details_for_selected(offers, selected_indices):
    """Dla wybranych ofert pobiera szczegóły (Playwright jako główna metoda)."""
    details = []
    for sel in selected_indices:
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
        
        log(f"  Pobieram szczegóły: {title[:60]}...")
        detail_file = os.path.join(DETAILS_DIR, f"detail_{idx}.json")
        
        # Sprawdź czy już mamy zapisane
        if os.path.exists(detail_file):
            with open(detail_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
            details.append(cached)
            log(f"    [CACHE] Wczytano z {detail_file}")
            continue
        
        html = fetch_offer_detail_playwright(url)
        if html:
            parsed = parse_offer_detail(html, url)
        else:
            parsed = None
        
        detail_entry = {
            "offer": offer,
            "detail_html_length": len(html) if html else 0,
            "detail_parsed": parsed,
            "detail_file": detail_file,
            "fetched_at": timestamp(),
        }
        details.append(detail_entry)
        
        # Zapisz cache
        with open(detail_file, "w", encoding="utf-8") as f:
            json.dump(detail_entry, f, ensure_ascii=False, indent=2)
        
        if parsed:
            log(f"    [OK] Pobrano: {parsed.get('title','?')[:60]}")
        else:
            log(f"    [WARN] Nie udało się sparsować szczegółów")
        
        time.sleep(1.5)  # Rate limiting
    
    return details

# ============================================================================
# KROK 5: AI Generowanie propozycji
# ============================================================================

def ai_generate_proposals(details):
    """Dla każdej wybranej oferty generuje propozycję przez DeepSeek."""
    proposals = []
    for i, d in enumerate(details):
        offer = d.get("offer", {})
        parsed = d.get("detail_parsed", {}) or {}
        
        title = parsed.get("title") or offer.get("title", "?")
        desc = parsed.get("full_desc") or offer.get("description", "")
        budget = parsed.get("budget") or offer.get("budget", "Do negocjacji")
        category = parsed.get("category") or offer.get("category", "")
        author = offer.get("author", "")
        
        prompt = (
            "Jesteś freelancerem-programistą Python. Poniżej dane oferty z Useme. "
            "Napisz profesjonalną, krótką propozycję (3-8 zdań) odpowiedzi na to zlecenie. "
            "Jeśli budżet jest 'Do negocjacji', zaproponuj realną stawkę godzinową lub za całość. "
            "Pisz w języku polskim, tonem profesjonalnym ale przyjaznym. "
            "Zwróć JSON z polami: proposal_text i proposed_rate.\n\n"
            f"Dane oferty:\n- Tytuł: {title}\n- Kategoria: {category}\n- Autor: {author}\n"
            f"- Budżet: {budget}\n- Opis: {desc[:2000]}\n\n"
            "Zwróć TYLKO surowy JSON (bez markdown, bez komentarzy)."
        )
        
        log(f"  Generuję propozycję dla: {title[:60]}...")
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
        "test": "TEST 06 – Pełny flow integracyjny",
        "timestamp_start": timestamp(),
        "status": "IN_PROGRESS",
        "steps": {},
    }
    
    print("=" * 70)
    print("  TEST 06 – Pełny flow integracyjny (Useme + AI)")
    print("=" * 70)
    
    # ─── Krok 1: Pobieranie listy ofert ───
    log("KROK 1: Pobieranie listy ofert...")
    html_content = None
    fetch_method = None
    
    # Próba Playwright (główna metoda – WebFetch niedostępne z poziomu Pythona)
    try:
        html_content = fetch_offers_playwright()
        fetch_method = "playwright"
    except Exception as e:
        log(f"[WARN] Playwright zawiódł: {e}")
    
    if not html_content:
        # Fallback: użyj zapisanego HTML z test01
        test01_html = os.path.join(BASE_DIR, "test01_connect", "page.html")
        if os.path.exists(test01_html):
            log(f"[FALLBACK] Używam zapisanego HTML z test01: {test01_html}")
            with open(test01_html, "r", encoding="utf-8") as f:
                html_content = f.read()
            fetch_method = "cached_test01"
    
    # Jeśli nadal nie ma HTML, spróbuj wczytać gotowy JSON z test02
    if not html_content:
        test02_json = os.path.join(BASE_DIR, "test02_parse_list", "offers.json")
        if os.path.exists(test02_json):
            log(f"[FALLBACK] Wczytuję gotowe oferty z test02: {test02_json}")
            with open(test02_json, "r", encoding="utf-8") as f:
                offers = json.load(f)
            fetch_method = "cached_test02_json"
            # Oznacz, że przeskakujemy parsowanie
            html_content = "__SKIP_PARSE__"
    
    if not html_content:
        log("[FATAL] Nie można pobrać HTML – ani Playwright, ani cache")
        flow_results["steps"]["1_fetch_list"] = {"status": "FAIL", "method": None, "offers_count": 0, "error": "Brak HTML"}
        flow_results["status"] = "FAIL"
        _save_and_print(flow_results)
        return 1
    
    # Zapisz HTML (tylko jeśli to faktycznie HTML)
    if html_content != "__SKIP_PARSE__":
        with open(LIST_HTML_FILE, "w", encoding="utf-8") as f:
            f.write(html_content)
        log(f"[OK] HTML zapisany: {LIST_HTML_FILE} ({len(html_content)} bajtów)")
        # Parsuj oferty
        offers = parse_offers_from_html(html_content)
    else:
        log(f"[INFO] Pomijam parsowanie – oferty wczytane z cache JSON")
    log(f"[OK] Sparsowano {len(offers)} ofert")
    
    with open(LIST_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(offers, f, ensure_ascii=False, indent=2)
    
    flow_results["steps"]["1_fetch_list"] = {
        "status": "OK",
        "method": fetch_method,
        "offers_count": len(offers),
        "html_size": len(html_content),
    }
    
    if len(offers) == 0:
        log("[FATAL] Zero ofert – przerywam")
        flow_results["status"] = "FAIL"
        _save_and_print(flow_results)
        return 1
    
    # ─── Krok 2: Marker nowych ofert ───
    log("\nKROK 2: Sprawdzanie markera nowych ofert...")
    has_new = check_marker(offers)
    flow_results["steps"]["2_marker"] = {
        "status": "OK",
        "has_new_offers": has_new,
        "first_offer_title": offers[0].get("title", "?")[:80],
    }
    
    # ─── Krok 3: AI Selekcja ───
    log("\nKROK 3: AI Selekcja ofert...")
    ai_selection = ai_select_offers(offers)
    
    with open(AI_SELECT_FILE, "w", encoding="utf-8") as f:
        json.dump(ai_selection, f, ensure_ascii=False, indent=2)
    
    selected_count = len(ai_selection.get("selected", []))
    rejected_count = len(ai_selection.get("rejected", []))
    is_fallback = ai_selection.get("fallback", False)
    log(f"[OK] AI wybrała: {selected_count} ofert, odrzuciła: {rejected_count}" + 
        (" (FALLBACK – bez AI)" if is_fallback else ""))
    
    flow_results["steps"]["3_ai_selection"] = {
        "status": "OK" if not is_fallback else "FALLBACK",
        "selected_count": selected_count,
        "rejected_count": rejected_count,
        "fallback": is_fallback,
    }
    
    # ─── Krok 4: Pobieranie szczegółów wybranych ofert ───
    log("\nKROK 4: Pobieranie szczegółów wybranych ofert...")
    selected = ai_selection.get("selected", [])
    # Ogranicz do MAX_DETAIL_OFFERS
    selected_to_fetch = selected[:MAX_DETAIL_OFFERS]
    details = fetch_details_for_selected(offers, selected_to_fetch)
    
    details_ok = sum(1 for d in details if d.get("detail_parsed"))
    log(f"[OK] Pobrano szczegóły: {details_ok}/{len(details)} ofert")
    
    flow_results["steps"]["4_fetch_details"] = {
        "status": "OK",
        "total": len(details),
        "success": details_ok,
        "failed": len(details) - details_ok,
    }
    
    # ─── Krok 5: AI Generowanie propozycji ───
    log("\nKROK 5: AI Generowanie propozycji...")
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
    
    flow_results["steps"]["5_ai_proposals"] = {
        "status": proposals_status,
        "generated": len([p for p in proposals if "error" not in p]) if proposals else 0,
        "total": len(proposals),
    }
    
    # ─── Krok 6: Zapis wyników i podsumowanie ───
    log("\nKROK 6: Zapis wyników końcowych...")
    
    flow_results["selected_offers"] = [
        {
            "index": s.get("index"),
            "title": s.get("title"),
            "reason": s.get("reason"),
        }
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


def _save_and_print(flow_results):
    """Zapisuje wyniki i wypisuje podsumowanie."""
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(flow_results, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 70)
    print("  PODSUMOWANIE TESTU 06")
    print("=" * 70)
    steps = flow_results.get("steps", {})
    
    s1 = steps.get("1_fetch_list", {})
    print(f"  1. Pobieranie listy:     {'✅' if s1.get('status')=='OK' else '❌'} ({s1.get('offers_count',0)} ofert, metoda: {s1.get('method','?')})")
    
    s2 = steps.get("2_marker", {})
    new_str = "NOWE" if s2.get("has_new_offers") else "BRAK NOWYCH"
    print(f"  2. Marker:               {'✅' if s2.get('status')=='OK' else '❌'} ({new_str})")
    
    s3 = steps.get("3_ai_selection", {})
    fb = " (FALLBACK)" if s3.get("fallback") else ""
    print(f"  3. AI Selekcja:          {'✅' if s3.get('status') in ('OK','FALLBACK') else '❌'} ({s3.get('selected_count',0)} wybranych{fb})")
    
    s4 = steps.get("4_fetch_details", {})
    print(f"  4. Pobieranie szczegółów: {'✅' if s4.get('status')=='OK' else '❌'} ({s4.get('success',0)}/{s4.get('total',0)})")
    
    s5 = steps.get("5_ai_proposals", {})
    print(f"  5. AI Propozycje:        {'✅' if s5.get('status')=='OK' else '⚠️'} ({s5.get('generated',0)}/{s5.get('total',0)})")
    
    status = flow_results.get("status", "?")
    print(f"\n  STATUS KOŃCOWY: {'✅' if status=='OK' else '❌'} {status}")
    
    # Wybrane oferty
    sel = flow_results.get("selected_offers", [])
    if sel:
        print(f"\n  WYBRANE OFERTY ({len(sel)}):")
        for s in sel:
            print(f"    - {s.get('title','?')[:80]}")
    
    # Propozycje
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