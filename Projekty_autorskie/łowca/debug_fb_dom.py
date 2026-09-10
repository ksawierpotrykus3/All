# -*- coding: utf-8 -*-
"""Diagnostyka DOM Facebooka dla konkretnego posta."""
import os
import sys
import json

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
URL = "https://www.facebook.com/adam.jesionkiewicz/posts/pfbid0rCq2GbdefzrfQejFPqPR7ZWVdMhfEZBR4phq124EcK9Kc19xxNqqDt6UxsM9puVHl"
POST_ID = "pfbid0rCq2GbdefzrfQejFPqPR7ZWVdMhfEZBR4phq124EcK9Kc19xxNqqDt6UxsM9puVHl"

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
    page.wait_for_timeout(6000)

    report = page.evaluate("""(postId) => {
        const out = [];
        const articles = Array.from(document.querySelectorAll('div[role="article"]'));
        out.push('LICZBA_ARTYKULOW=' + articles.length);
        articles.forEach((art, i) => {
            const text = (art.innerText || '').replace(/\\s+/g, ' ').slice(0, 180);
            let hrefs = [];
            art.querySelectorAll('a[href]').forEach(a => {
                const h = a.getAttribute('href') || '';
                if (h.includes('pfbid') || h.includes('/posts/') || h.includes('/reel/') || h.includes('/videos/') || h.includes('/groups/')) {
                    hrefs.push(h.slice(0, 120));
                }
            });
            hrefs = hrefs.slice(0, 6);
            // dane z data-store (tylko klucze)
            let storeKeys = [];
            const ds = art.getAttribute('data-store');
            if (ds) {
                try {
                    const obj = JSON.parse(ds);
                    storeKeys = Object.keys(obj).slice(0, 40);
                } catch (e) {
                    storeKeys = ['PARSE_ERR'];
                }
            }
            out.push('--- ARTYKUL ' + i + ' ---');
            out.push('aria-posinset=' + (art.getAttribute('aria-posinset') || ''));
            out.push('data-pagelet=' + (art.getAttribute('data-pagelet') || art.closest('[data-pagelet]')?.getAttribute('data-pagelet') || ''));
            out.push('czy_zawiera_postId=' + (art.innerHTML.includes(postId) ? 'TAK' : 'nie'));
            out.push('storeKeys=' + storeKeys.join(', '));
            out.push('hrefs=' + hrefs.join(' | '));
            out.push('text=' + text);
        });
        return out.join('\\n');
    }""", POST_ID)

    out_path = os.path.join(SCRIPT_DIR, "debug_fb_dom_report.txt")
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print("Zapisano raport: " + out_path)
    print(report[:3000])
    browser.close()