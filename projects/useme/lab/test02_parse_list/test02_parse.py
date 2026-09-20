"""
TEST 02 – Parsowanie listy ofert z Useme
Wczytuje HTML z test01, parsuje oferty, zapisuje JSON.
"""
import json
import os
import re
from datetime import datetime
from bs4 import BeautifulSoup

# Ścieżki
BASE_DIR = r"c:\Users\Ksawier\Pictures\Screenshots\useme\lab"
HTML_PATH = os.path.join(BASE_DIR, "test01_connect", "page.html")
OUTPUT_DIR = os.path.join(BASE_DIR, "test02_parse_list")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "offers.json")
MAX_OFFERS = 10

# Pełna ścieżka do katalogu wyjściowego
os.makedirs(OUTPUT_DIR, exist_ok=True)


def parse_offers(html_content):
    """Parsuje HTML i zwraca listę słowników z danymi ofert."""
    soup = BeautifulSoup(html_content, "html.parser")
    job_articles = soup.select("article.job")
    
    offers = []
    for article in job_articles:
        if len(offers) >= MAX_OFFERS:
            break
        
        try:
            offer = {}
            
            # --- TYTUŁ + LINK ---
            title_el = article.select_one("a.job__title-link")
            if title_el:
                offer["title"] = title_el.get_text(strip=True)
                href = title_el.get("href", "")
                # Buduj pełny URL
                if href.startswith("/"):
                    offer["url"] = f"https://useme.com{href}"
                else:
                    offer["url"] = href
            else:
                offer["title"] = None
                offer["url"] = None
            
            # --- NAZWA ZLECENIODAWCY ---
            author_el = article.select_one("div.job__headline strong")
            if author_el:
                offer["author"] = author_el.get_text(strip=True)
            else:
                offer["author"] = None
            
            # --- AVATAR (czy jest zdjęcie) ---
            avatar_wrapper = article.select_one("div.user_avatar")
            has_avatar = False
            if avatar_wrapper:
                # Jeśli klasa zawiera user_avatar__default-image, to brak avatara
                classes = avatar_wrapper.get("class", [])
                has_avatar = "user_avatar__default-image" not in classes
            offer["has_avatar"] = has_avatar
            
            # --- LICZBA WYSŁANYCH OFERT ---
            offers_el = article.select_one("div.job__header-details--offers span:last-child")
            if offers_el:
                offers_text = offers_el.get_text(strip=True)
                try:
                    offer["offers_count"] = int(offers_text)
                except ValueError:
                    offer["offers_count"] = offers_text
            else:
                offer["offers_count"] = None
            
            # --- CZAS DO WYGAŚNIĘCIA ---
            date_el = article.select_one("div.job__header-details--date span:last-child")
            if date_el:
                offer["expiry"] = date_el.get_text(strip=True)
            else:
                offer["expiry"] = None
            
            # --- KATEGORIA SZCZEGÓŁOWA ---
            category_el = article.select_one("div.job__category a p")
            if category_el:
                offer["category"] = category_el.get_text(strip=True)
            else:
                # Fallback: spróbuj samego div.job__category
                cat_div = article.select_one("div.job__category")
                if cat_div:
                    offer["category"] = cat_div.get_text(strip=True)
                else:
                    offer["category"] = None
            
            # --- BUDŻET ---
            budget_el = article.select_one("span.job__budget-value")
            if budget_el:
                budget_text = budget_el.get_text(strip=True)
                # Usuń zbędne spacje
                offer["budget"] = re.sub(r"\s+", " ", budget_text)
            else:
                offer["budget"] = None
            
            # --- KRÓTKI OPIS (pierwsze ~200 znaków) ---
            desc_el = article.select_one("div.job__content p")
            if desc_el:
                full_desc = desc_el.get_text(strip=True)
                offer["description"] = full_desc[:200]
            else:
                offer["description"] = None
            
            offers.append(offer)
            
        except Exception as e:
            print(f"  [WARN] Błąd parsowania oferty: {e}")
            continue
    
    return offers


def main():
    print("=" * 60)
    print("TEST 02 – Parsowanie listy ofert z Useme")
    print("=" * 60)
    
    # Sprawdź istnienie pliku HTML
    if not os.path.exists(HTML_PATH):
        print(f"[ERROR] Plik HTML nie istnieje: {HTML_PATH}")
        return 1
    
    print(f"\n[INFO] Wczytywanie HTML z: {HTML_PATH}")
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    print(f"[INFO] Rozmiar HTML: {len(html_content)} bajtów")
    
    # Parsuj
    print("\n[INFO] Parsowanie ofert...")
    offers = parse_offers(html_content)
    
    print(f"\n[INFO] Znaleziono ofert: {len(offers)}/{MAX_OFFERS}")
    
    # Wyświetl selektory CSS
    print("\n--- ZNALEZIONE SELEKTORY CSS ---")
    print(f'  Kontener oferty:    article.job')
    print(f'  Tytuł + link:       a.job__title-link')
    print(f'  Autor:              div.job__headline strong')
    print(f'  Avatar:             div.user_avatar (sprawdzanie user_avatar__default-image)')
    print(f'  Liczba ofert:       div.job__header-details--offers span:last-child')
    print(f'  Czas wygaśnięcia:   div.job__header-details--date span:last-child')
    print(f'  Kategoria:          div.job__category a p')
    print(f'  Budżet:             span.job__budget-value')
    print(f'  Opis:               div.job__content p')
    
    # Wyświetl podsumowanie każdej oferty
    print("\n--- PODSUMOWANIE OFERT ---")
    for i, offer in enumerate(offers, 1):
        print(f"\n  Oferta #{i}:")
        print(f'    Tytuł:      {offer.get("title", "N/A")}')
        print(f'    Autor:      {offer.get("author", "N/A")}')
        print(f'    Avatar:     {"TAK" if offer.get("has_avatar") else "NIE"}')
        print(f'    Oferty:     {offer.get("offers_count", "N/A")}')
        print(f'    Wygasa:     {offer.get("expiry", "N/A")}')
        print(f'    Kategoria:  {offer.get("category", "N/A")}')
        print(f'    Budżet:     {offer.get("budget", "N/A")}')
        print(f'    Opis:       {offer.get("description", "N/A")[:80]}...')
        print(f'    URL:        {offer.get("url", "N/A")}')
    
    # Zapisz do JSON
    print(f"\n[INFO] Zapisywanie wyników do: {OUTPUT_PATH}")
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(offers, f, ensure_ascii=False, indent=2)
    
    print("[OK] Zapisano pomyślnie!")
    print(f"\nPełna ścieżka JSON: {OUTPUT_PATH}")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    exit(main())