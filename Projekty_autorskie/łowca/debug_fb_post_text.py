# -*- coding: utf-8 -*-
"""Diagnostyka: zlokalizuj dokladny element z trescia glownego posta FB."""
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
URL = "https://www.facebook.com/adam.jesionkiewicz/posts/pfbid0rCq2GbdefzrfQejFPqPR7ZWVdMhfEZBR4phq124EcK9Kc19xxNqqDt6UxsM9puVHl"

from playwright.sync_api import sync_playwright

cookie_path = os.path.join(SCRIPT_DIR, "cookies.txt")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 1000}
    )
    if os.path.exists(cookie_path):
        fb_cookies = []
        with open(cookie_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split('\t')
                if len(parts) >= 7 and 'facebook' in parts[0]:
                    domain, flag, path, secure, expiry, name, value = parts[:7]
                    try:
                        exp_int = int(expiry) if expiry and expiry != '0' else None
                    except ValueError:
                        exp_int = None
                    c_dict = {
                        'name': name, 'value': value,
                        'domain': domain.replace('#HttpOnly_', ''),
                        'path': path, 'secure': secure.upper() == 'TRUE'
                    }
                    if exp_int and exp_int > 0:
                        c_dict['expires'] = exp_int
                    fb_cookies.append(c_dict)
        if fb_cookies:
            context.add_cookies(fb_cookies)

    page = context.new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=35000)
    page.wait_for_timeout(9000)

    # Przewinięcie, aby wymusić doczytanie posta
    page.mouse.wheel(0, 2000)
    page.wait_for_timeout(2000)
    page.mouse.wheel(0, -2000)
    page.wait_for_timeout(2000)

    report = page.evaluate("""() => {
        const out = [];

        // 1. Pelnia tresc dialogu (skrocona)
        const dialog = document.querySelector('div[role="dialog"]');
        if (dialog) {
            out.push('=== DIALOG INNERTEXT (pierwsze 3000 znakow) ===');
            out.push((dialog.innerText || '').replace(/\\s+/g, ' ').slice(0, 3000));
            out.push('=== KONIEC DIALOGU ===');
        } else {
            out.push('=== BRAK DIALOGU ===');
        }

        // 2. Elementy zawierajace 'Pewnie' lub 'tworzenie' lub 'Genesis' lub 'WhiteRhino'
        const needles = ['pewnie slyszeliscie', 'tworzenie software', 'genesis eva', 'whiterhino'];
        for (const needle of needles) {
            out.push('=== SZUKAM: ' + needle + ' ===');
            const hits = Array.from(document.querySelectorAll('div, span, p, article, section')).filter(el => {
                const t = (el.innerText || '').toLowerCase();
                return t.includes(needle) && t.length < 8000;
            });
            out.push('LICZBA=' + hits.length);
            hits.slice(0, 12).forEach((el, i) => {
                let desc = el.tagName.toLowerCase();
                const role = el.getAttribute('role');
                const cls = (el.getAttribute('class') || '').slice(0, 80);
                if (role) desc += '[role=' + role + ']';
                if (cls) desc += '.' + cls.replace(/\\s+/g, '.');
                out.push('-- hit ' + i + ' ' + desc);
                out.push('   text=' + (el.innerText || '').replace(/\\s+/g, ' ').slice(0, 250));
            });
        }

        return out.join('\\n');
    }""")

    out_path = os.path.join(SCRIPT_DIR, "debug_fb_post_text_report.txt")
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print("Zapisano raport: " + out_path)
    print(report[:5000])
    browser.close()