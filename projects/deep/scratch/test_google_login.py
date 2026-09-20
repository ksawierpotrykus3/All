import time
import sys
from pathlib import Path
from DrissionPage import ChromiumPage, ChromiumOptions

data_dir = Path(__file__).parent / ".test_chrome_profile"
data_dir.mkdir(parents=True, exist_ok=True)

opt = ChromiumOptions()
opt.set_user_data_path(str(data_dir))
opt.set_argument("--no-first-run")
opt.set_argument("--no-default-browser-check")
opt.set_argument("--disable-blink-features=AutomationControlled")
opt.set_argument("--window-size=1280,900")
opt.auto_port()

print("[1] Uruchamiam Chromium...", flush=True)
page = ChromiumPage(opt)
try:
    print("[2] Otwieram accounts.google.com...", flush=True)
    page.get("https://accounts.google.com")
    time.sleep(3)
    
    print("[3] Sprawdzam strone...", flush=True)
    print("URL:", page.url, flush=True)
    print("Title:", page.title, flush=True)
    
    # Szukamy pol wejsciowych
    inputs = page.eles("tag:input")
    print(f"Znaleziono {len(inputs)} pol input:")
    for inp in inputs:
        print("  input:", inp.attrs, "visible=", inp.states.is_displayed, flush=True)
        
    body_text = page.ele("tag:body").text if page.ele("tag:body") else ""
    lines = [l.strip() for l in body_text.splitlines() if l.strip()]
    print("\nPierwsze 20 linii strony:", flush=True)
    for l in lines[:20]:
        try:
            print("  |", l.encode('ascii', 'replace').decode('ascii'), flush=True)
        except Exception:
            pass
            
    # Sprawdz czy jest captcha lub blokada
    if "widzisz lub" in body_text or "Wpisz tekst" in body_text:
        print("\n[!] WYKRYTO CAPTCHA GOOGLE: Google wymaga rozwiazania captchy (Wpisz tekst ktory widzisz lub slyszysz) juz na wejsciu!", flush=True)
        
    ident_input = page.ele("css:input#identifierId") or page.ele("css:input[type=email]")
    if ident_input:
        print("[4] Wpisuje pawelkowalkp@gmail.com...", flush=True)
        ident_input.input("pawelkowalkp@gmail.com")
        time.sleep(1)
        next_btn = page.ele("xpath://button[contains(., 'Dalej') or contains(., 'Next')]") or page.ele("css:#identifierNext")
        if next_btn:
            print("[5] Klikam Dalej...", flush=True)
            next_btn.click()
            time.sleep(4)
            print("URL po Dalej:", page.url, flush=True)
            body_after = page.ele("tag:body").text if page.ele("tag:body") else ""
            print("Fragment tekstu po kliknieciu Dalej:", flush=True)
            for l in [l.strip() for l in body_after.splitlines() if l.strip()][:20]:
                try:
                    print("  |", l.encode('ascii', 'replace').decode('ascii'), flush=True)
                except Exception:
                    pass
            if "mo?e nie by? bezpieczna" in body_after.encode('ascii', 'replace').decode('ascii') or "bezpieczna" in body_after:
                print("\n[!] WYNIK: Google zablokowalo logowanie: 'Ta przegladarka lub aplikacja moze nie byc bezpieczna'!", flush=True)
            elif "has?o" in body_after.lower() or "password" in body_after.lower():
                print("\n[+] WYNIK: Google pozwolilo przejsc do hasla!", flush=True)
            else:
                print("\n[?] Inny stan strony po kliknieciu Dalej.", flush=True)
finally:
    try:
        page.quit()
    except Exception:
        pass
