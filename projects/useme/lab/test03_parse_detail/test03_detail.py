"""
Test 03 – Wchodzenie w ofertę i pełny opis.
Kliknięcie w pierwszą ofertę, kliknięcie "pokaż pełny opis", pobranie danych szczegółowych.
Używa Playwright sync z Firefoxem.
"""

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import json
import time
import os
from datetime import datetime

# Ścieżki
BASE_DIR = r"c:\Users\Ksawier\Pictures\Screenshots\useme\lab\test03_parse_detail"
DETAIL_JSON_PATH = os.path.join(BASE_DIR, "detail.json")
DETAIL_HTML_PATH = os.path.join(BASE_DIR, "detail_page.html")

CATEGORY_URL = "https://useme.com/pl/jobs/category/programowanie-i-it,35/"

def safe_text(page, selector, default=""):
    """Bezpiecznie pobiera tekst z selektora."""
    try:
        el = page.query_selector(selector)
        if el:
            return el.inner_text().strip()
    except:
        pass
    return default

def safe_text_all(page, selector):
    """Bezpiecznie pobiera teksty ze wszystkich pasujących elementów."""
    try:
        els = page.query_selector_all(selector)
        return [el.inner_text().strip() for el in els if el.inner_text().strip()]
    except:
        pass
    return []

def safe_attr(page, selector, attr, default=""):
    """Bezpiecznie pobiera atrybut z selektora."""
    try:
        el = page.query_selector(selector)
        if el:
            return el.get_attribute(attr) or default
    except:
        pass
    return default

def extract_skills(page):
    """Próbuje znaleźć umiejętności na stronie."""
    skills_selectors = [
        '.job-skills .skill-tag',
        '.skills-list .skill',
        '.tag-list .tag',
        '[class*="skill"]',
        'a[href*="/jobs/skill/"]',
        '.offer-skills span',
        '.job-tags .tag',
        '.job__tags .tag',
    ]
    for selector in skills_selectors:
        skills = safe_text_all(page, selector)
        if skills:
            return skills
    return []

def extract_detail_data(page):
    """Ekstrakcja wszystkich danych ze strony szczegółów."""
    data = {}

    # --- Tytuł ---
    title_selectors = [
        'h1', 'h1.job__title', 'h1.offer-title', '.job-title h1',
        '.offer-header h1', '[class*="title"] h1', 'h1[class*="title"]',
    ]
    data["title"] = ""
    for sel in title_selectors:
        t = safe_text(page, sel)
        if t:
            data["title"] = t
            break

    # --- Autor ---
    author_selectors = [
        '.job__author-name', '.offer-author', '.author-name',
        '[class*="author"] span', 'a[class*="author"]',
        '.job-author a', '.user-name',
    ]
    data["author"] = ""
    for sel in author_selectors:
        a = safe_text(page, sel)
        if a:
            data["author"] = a
            break

    # --- Data opublikowania ---
    published_selectors = [
        '.job__published', '.offer-published', '.job-date',
        '[class*="published"]', '.offer-meta time',
        'time', '.job__meta-item:has-text("opublikowano")',
        'span:has-text("godzin"), span:has-text("dni"), span:has-text("minut")',
        '.job__meta time[datetime]',
    ]
    data["published"] = ""
    for sel in published_selectors:
        p = safe_text(page, sel)
        if p and ("temu" in p.lower() or "godzin" in p.lower() or "dni" in p.lower() or "minut" in p.lower()):
            data["published"] = p
            break
    if not data["published"]:
        # Szukamy daty w dowolnym miejscu
        try:
            body_text = page.inner_text("body")
            import re
            match = re.search(r'(\d+\s+(godzin|dni|minut|godziny|dnia|minuty)\s+temu)', body_text, re.IGNORECASE)
            if match:
                data["published"] = match.group(1)
        except:
            pass

    # --- Kategoria ---
    category_selectors = [
        '.job__category', '.offer-category', '.breadcrumb li:last-child',
        '.breadcrumb a:last-child', '[class*="category"] a',
        '.job-meta-category', 'a[href*="/category/"]',
    ]
    data["category"] = ""
    for sel in category_selectors:
        c = safe_text(page, sel)
        if c:
            data["category"] = c
            break

    # --- Prawa autorskie ---
    copyright_selectors = [
        'text=prawa autorskie', 'text=praw autorskich',
        '.copyright-info', '[class*="copyright"]',
        '.job-copyright', 'span:has-text("praw")',
    ]
    data["copyright"] = ""
    for sel in copyright_selectors:
        try:
            el = page.query_selector(sel)
            if el:
                data["copyright"] = el.inner_text().strip()
                break
        except:
            pass
    if not data["copyright"]:
        # Szukamy w tekście body
        try:
            body = page.inner_text("body")
            if "przeniesienie praw autorskich" in body.lower():
                data["copyright"] = "Przeniesienie praw autorskich"
            elif "prawa autorskie" in body.lower():
                data["copyright"] = "Prawa autorskie – znaleziono wzmiankę"
        except:
            pass

    # --- Krótki opis (z opisu bez rozwinięcia) ---
    desc_selectors = [
        '.job__description', '.offer-description', '.job-description',
        '[class*="description"]', '.offer-content', '.job-content',
        '.offer-details', '#job-description',
    ]
    data["short_desc"] = ""
    for sel in desc_selectors:
        d = safe_text(page, sel)
        if d and len(d) > 20:
            data["short_desc"] = d[:500]  # pierwsze 500 znaków
            break

    # --- Pełny opis (po kliknięciu "pokaż pełny opis") ---
    full_desc_selectors = [
        '.job__description', '.offer-description', '.job-description',
        '[class*="description"]', '.offer-content', '.job-content',
        '.offer-details', '#job-description',
        '.full-description', '[class*="full-desc"]',
        'div[class*="description-full"]',
    ]
    data["full_desc"] = ""
    for sel in full_desc_selectors:
        d = safe_text(page, sel)
        if d and len(d) > 50:
            data["full_desc"] = d
            break

    # --- Umiejętności ---
    data["skills"] = extract_skills(page)

    # --- Dane z menu prawego (budżet, ważne przez) ---
    # Budżet – różne możliwe lokalizacje
    budget_selectors = [
        '.job__budget', '.offer-budget', '.job-budget',
        '[class*="budget"] span', '.budget-value',
        '.offer-sidebar .budget', '.job-sidebar .budget',
        '.sidebar-item:has-text("Budżet") span',
        '.sidebar-item:has-text("budżet") span',
        'div:has(> span:text("Budżet")) span:last-child',
        'div:has(> span:text("budżet")) span:last-child',
        '.info-box .price',
    ]
    data["budget"] = ""
    for sel in budget_selectors:
        try:
            el = page.query_selector(sel)
            if el:
                b = el.inner_text().strip()
                if b and any(c.isdigit() for c in b):
                    data["budget"] = b
                    break
        except:
            pass
    if not data["budget"]:
        # Szukamy w całym body tekstu z kwotą
        try:
            import re
            body = page.inner_text("body")
            match = re.search(r'(Budżet|budżet)\s*[:\-]?\s*([\d\s,.]+\s*(PLN|zł|EUR|USD)?)', body)
            if match:
                data["budget"] = match.group(2).strip()
        except:
            pass

    # --- Ważne przez (expiry) ---
    expiry_selectors = [
        '.job__expiry', '.offer-expiry', '.job-expiry',
        '[class*="expiry"]', '.sidebar-item:has-text("ważne") span',
        '.sidebar-item:has-text("Ważne") span',
        'div:has(> span:text("Ważne")) span:last-child',
        'div:has(> span:text("ważne")) span:last-child',
        '.info-box .expiry',
    ]
    data["expires"] = ""
    for sel in expiry_selectors:
        try:
            el = page.query_selector(sel)
            if el:
                e = el.inner_text().strip()
                if e and ("dni" in e.lower() or "dzień" in e.lower() or "tygodni" in e.lower()):
                    data["expires"] = e
                    break
        except:
            pass
    if not data["expires"]:
        try:
            import re
            body = page.inner_text("body")
            match = re.search(r'(Ważne|ważne)\s*(przez)?\s*[:\-]?\s*(\d+\s*(dni|dzień|tygodni|tydzień))', body, re.IGNORECASE)
            if match:
                data["expires"] = match.group(3).strip()
        except:
            pass

    # --- Liczba ofert (może być widoczna) ---
    offers_count_selectors = [
        '.job__offers-count', '.offer-count', '.offers-count',
        'span:has-text("ofert")',
    ]
    data["offers_count"] = ""
    for sel in offers_count_selectors:
        try:
            el = page.query_selector(sel)
            if el:
                txt = el.inner_text().strip()
                import re
                m = re.search(r'(\d+)', txt)
                if m:
                    data["offers_count"] = int(m.group(1))
                    break
        except:
            pass

    # --- Przycisk "Dodaj ofertę" ---
    add_offer_selectors = [
        'a:has-text("Dodaj ofertę")',
        'button:has-text("Dodaj ofertę")',
        'a:has-text("Wyślij ofertę")',
        'button:has-text("Wyślij ofertę")',
        'a:has-text("Aplikuj")',
        'button:has-text("Aplikuj")',
        '.btn-add-offer', '.btn-apply',
        '[class*="apply"]', '[class*="add-offer"]',
    ]
    data["add_offer_button_found"] = False
    data["add_offer_button_text"] = ""
    for sel in add_offer_selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                data["add_offer_button_found"] = True
                data["add_offer_button_text"] = el.inner_text().strip()
                break
        except:
            pass

    # --- Data zapisu ---
    data["scraped_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data["source_url"] = page.url

    return data


def dismiss_cookie_banner(page):
    """Próbuje zamknąć/zaakceptować baner cookies."""
    cookie_selectors = [
        '#cookiescript_accept',
        '#cookiescript_injected_wrapper #cookiescript_accept',
        'button:has-text("Akceptuj wszystkie")',
        'button:has-text("Akceptuj")',
        'button:has-text("Zgadzam się")',
        'a:has-text("Akceptuj")',
        '#cookiescript_close',
        '[data-cs-i18n-text*="Akceptuj"]',
        '.cookiescript_accept',
    ]
    for sel in cookie_selectors:
        try:
            btn = page.query_selector(sel)
            if btn and btn.is_visible():
                print(f"    Zamykam baner cookies: {sel}")
                # Użyj evaluate do kliknięcia, aby ominąć intercept
                btn.evaluate("el => el.click()")
                page.wait_for_timeout(1000)
                return True
        except:
            continue
    # Spróbuj przez JavaScript ukryć baner
    try:
        page.evaluate("""
            var banner = document.getElementById('cookiescript_injected_wrapper');
            if (banner) { banner.style.display = 'none'; }
        """)
        page.wait_for_timeout(500)
        return True
    except:
        pass
    return False


def get_offer_url_from_page(page):
    """Pobiera absolutny URL pierwszej oferty ze strony kategorii."""
    link_selectors = [
        'a.job__title-link',
        'a[class*="job__title"]',
        'a.offer-title-link',
        '.job-item a[class*="title"]',
        '.offer-list-item a[class*="title"]',
        'h2 a[href*="/pl/jobs/"]', 'h3 a[href*="/pl/jobs/"]',
        '.job-listing a[href*="/pl/jobs/"]',
        'a[href*="/pl/jobs/"][class*="title"]',
    ]
    for selector in link_selectors:
        try:
            el = page.query_selector(selector)
            if el:
                href = el.get_attribute("href")
                if href and "/pl/jobs/" in href:
                    # Zapewnij absolutny URL
                    if href.startswith("/"):
                        return "https://useme.com" + href
                    return href
        except:
            continue
    return None


def main():
    print("[TEST 03] Rozpoczynam test – wchodzenie w ofertę i pełny opis...")

    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0"
        )
        page = context.new_page()

        try:
            # 1. Wejdź na stronę kategorii
            print("[*] Wchodzę na stronę kategorii...")
            page.goto(CATEGORY_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(5000)

            # 1a. Zamknij baner cookies
            dismiss_cookie_banner(page)

            # 2. Pobierz URL pierwszej oferty (zamiast klikać)
            print("[*] Pobieram URL pierwszej oferty...")
            first_offer_url = get_offer_url_from_page(page)

            if not first_offer_url:
                # Awaryjnie – pobieramy pierwszy link z offers.json
                print("[!] Nie znaleziono linku na stronie. Używam offers.json...")
                with open(r"c:\Users\Ksawier\Pictures\Screenshots\useme\lab\test02_parse_list\offers.json", "r", encoding="utf-8") as f:
                    offers = json.load(f)
                if offers:
                    first_offer_url = offers[0]["url"]
                else:
                    raise Exception("Brak ofert w offers.json")

            print(f"    Przechodzę do: {first_offer_url}")
            page.goto(first_offer_url, wait_until="domcontentloaded", timeout=30000)

            # 3. Czekamy na załadowanie strony szczegółów
            print("[*] Czekam na stronę szczegółów...")
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(3000)

            current_url = page.url
            print(f"    Aktualny URL: {current_url}")

            # 4. Zapisz HTML strony szczegółów
            print("[*] Zapisuję HTML strony szczegółów...")
            detail_html = page.content()
            os.makedirs(BASE_DIR, exist_ok=True)
            with open(DETAIL_HTML_PATH, "w", encoding="utf-8") as f:
                f.write(detail_html)
            print(f"    HTML zapisany: {DETAIL_HTML_PATH}")

            # 5. Spróbuj znaleźć i kliknąć "pokaż pełny opis"
            show_more_clicked = False
            show_more_selectors = [
                'text=pokaż pełny opis',
                'text=zobacz pełny opis',
                'text=Pokaż pełny opis',
                'text=Zobacz pełny opis',
                'text=pełny opis',
                'text=Pełny opis',
                'text=pokaż więcej',
                'text=Pokaż więcej',
                'text=czytaj więcej',
                'text=Czytaj więcej',
                'button:has-text("pełny")',
                'a:has-text("pełny")',
                'span:has-text("pełny opis")',
                '[class*="show-more"]',
                '[class*="read-more"]',
                '[class*="expand"]',
                'button:has-text("więcej")',
                'a:has-text("więcej")',
                '.job__description-show-more',
                '.description-expand',
                '.show-full-description',
            ]

            for sel in show_more_selectors:
                try:
                    el = page.query_selector(sel)
                    if el and el.is_visible():
                        print(f"[*] Klikam 'pokaż pełny opis' (selektor: {sel})...")
                        el.click()
                        show_more_clicked = True
                        page.wait_for_timeout(2000)
                        break
                except:
                    continue

            if not show_more_clicked:
                # Spróbuj get_by_text
                try:
                    btn = page.get_by_text("pełny opis", exact=False).first
                    if btn:
                        btn.click()
                        show_more_clicked = True
                        print("[*] Kliknięto 'pokaż pełny opis' przez get_by_text")
                        page.wait_for_timeout(2000)
                except:
                    pass

            if not show_more_clicked:
                print("[!] Nie znaleziono przycisku 'pokaż pełny opis' – pobieram dostępny opis")

            # 6. Poczekaj jeszcze chwilę po ewentualnym rozwinięciu
            page.wait_for_timeout(2000)

            # 7. Pobierz dane
            print("[*] Ekstrakcja danych ze strony szczegółów...")
            detail_data = extract_detail_data(page)

            # 8. Zapisz do JSON
            with open(DETAIL_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(detail_data, f, ensure_ascii=False, indent=2)
            print(f"    Dane zapisane: {DETAIL_JSON_PATH}")

            # Podsumowanie
            print("\n[=== PODSUMOWANIE ===")
            print(f"  URL: {detail_data.get('source_url', 'N/A')}")
            print(f"  Tytuł: {detail_data.get('title', 'N/A')}")
            print(f"  Autor: {detail_data.get('author', 'N/A')}")
            print(f"  Opublikowano: {detail_data.get('published', 'N/A')}")
            print(f"  Kategoria: {detail_data.get('category', 'N/A')}")
            print(f"  Prawa autorskie: {detail_data.get('copyright', 'N/A')}")
            print(f"  Budżet: {detail_data.get('budget', 'N/A')}")
            print(f"  Ważne przez: {detail_data.get('expires', 'N/A')}")
            print(f"  Umiejętności: {detail_data.get('skills', [])}")
            print(f"  Przycisk 'Dodaj ofertę': {'✅ Znaleziony' if detail_data.get('add_offer_button_found') else '❌ Nie znaleziony'}")
            if detail_data.get('add_offer_button_text'):
                print(f"    Tekst przycisku: {detail_data['add_offer_button_text']}")
            print(f"  Krótki opis (pierwsze 200 znaków): {detail_data.get('short_desc', '')[:200]}...")
            print(f"  Pełny opis (długość): {len(detail_data.get('full_desc', ''))} znaków")
            print(f"  'Pokaż pełny opis' kliknięty: {'Tak' if show_more_clicked else 'Nie'}")

            print("\n[TEST 03] ✅ Zakończono pomyślnie!")

        except Exception as e:
            print(f"\n[TEST 03] ❌ BŁĄD: {e}")
            import traceback
            traceback.print_exc()

            # Zapisz co się da nawet przy błędzie
            try:
                error_data = {
                    "error": str(e),
                    "url": page.url if page else "",
                    "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                with open(DETAIL_JSON_PATH, "w", encoding="utf-8") as f:
                    json.dump(error_data, f, ensure_ascii=False, indent=2)
            except:
                pass

        finally:
            browser.close()
            print("[*] Przeglądarka zamknięta.")


if __name__ == "__main__":
    main()