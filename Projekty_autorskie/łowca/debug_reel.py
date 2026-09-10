import sys, os, time
sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
from playwright.sync_api import sync_playwright

URL = "https://www.facebook.com/reel/1540571997279754/"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_PATH = os.path.join(SCRIPT_DIR, "cookies.txt")

def load_cookies(ctx):
    ck = []
    with open(COOKIE_PATH, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            p = line.split('\t')
            if len(p) >= 7 and 'facebook' in p[0]:
                domain, flag, path, secure, expiry, name, value = p[:7]
                try:
                    exp = int(expiry) if expiry and expiry != '0' else None
                except ValueError:
                    exp = None
                d = {'name': name, 'value': value, 'domain': domain.replace('#HttpOnly_', ''),
                     'path': path, 'secure': secure.upper() == 'TRUE'}
                if exp and exp > 0:
                    d['expires'] = exp
                ck.append(d)
    if ck:
        ctx.add_cookies(ck)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        viewport={"width": 1366, "height": 900},
        locale="pl-PL",
    )
    load_cookies(ctx)
    page = ctx.new_page()
    print("-> goto")
    page.goto(URL, wait_until="domcontentloaded", timeout=40000)
    page.wait_for_timeout(6000)
    print("-> page title:", page.title())
    print("-> url:", page.url)

    # kliknij przycisk komentarzy / otwórz panel
    clicked_comment = False
    for label in ["Komentarze", "Comments", "komentarze", "comments"]:
        try:
            loc = page.locator(f'div[role="button"]:has-text("{label}")')
            if loc.count() > 0:
                loc.first.click(timeout=4000)
                print(f"-> kliknięto przycisk komentarzy: {label}")
                page.wait_for_timeout(4000)
                clicked_comment = True
                break
        except Exception as e:
            print("-> err klik", label, repr(e))

    # pętla przewijania i doczytywania (kończy wcześniej, gdy nie przybywa komentarzy)
    prev_count = 0
    stuck = 0
    for i in range(25):
        try:
            page.mouse.wheel(0, 5000)
            page.evaluate("""() => {
                const d = document.querySelector('div[role="dialog"]');
                if (d) d.scrollTop = d.scrollHeight;
                window.scrollBy(0, 5000);
            }""")
        except Exception:
            pass
        page.wait_for_timeout(700)
        try:
            page.evaluate("""() => {
                const bs = Array.from(document.querySelectorAll('div[role="button"], span, a'));
                for (const b of bs) {
                    const t = (b.innerText || '').toLowerCase();
                    if (/(zobacz więcej komentarzy|view more comments|więcej komentarzy|more comments|wyświetl więcej komentarzy|zobacz kolejne komentarze)/.test(t)) {
                        b.click();
                        return true;
                    }
                }
                return false;
            }""")
        except Exception:
            pass
        page.wait_for_timeout(500)

        curr_count = page.locator('div[role="article"]').count()
        if curr_count == prev_count:
            stuck += 1
        else:
            stuck = 0
            prev_count = curr_count
        if stuck >= 3 and curr_count > 0:
            print(f"-> przerwano po {i + 1} rundach (brak nowych komentarzy)")
            break

    n_articles = page.locator('div[role="article"]').count()
    n_dialogs = page.locator('div[role="dialog"]').count()
    print("-> articles:", n_articles)
    print("-> dialogs:", n_dialogs)

    # zapisz tylko wyekstrahowany tekst komentarzy (zamiast całego HTML — unikamy zrzutu ~2,6 MB)
    texts = page.evaluate("""() => {
        const arts = Array.from(document.querySelectorAll('div[role="article"]'));
        return arts.map(a => (a.innerText || '').trim()).filter(t => t.length > 0);
    }""")
    out_txt = os.path.join(SCRIPT_DIR, "debug_reel_tresc.txt")
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write("\n\n---\n\n".join(texts))
    print("-> zapisano", out_txt, "artykułów:", len(texts))

    browser.close()