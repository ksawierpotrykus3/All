from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_page(viewport={'width': 1440, 'height': 900})
    url = 'https://www.olx.pl/d/oferta/iphone-16-pro-128-gb-desert-titanium-apple-certified-gwarancja-apple-12m-100-bateria-zaplombowany-CID99-ID1bKmCJ.html'
    page.goto(url, wait_until='domcontentloaded', timeout=25000)
    page.wait_for_timeout(2000)
    try:
        page.locator('#onetrust-accept-btn-handler').first.click(timeout=1000)
    except Exception:
        pass

    btns = page.locator('button, a')
    count = btns.count()
    print(f"Total interactive elements: {count}")
    for i in range(count):
        txt = btns.nth(i).inner_text().strip()
        if "Kup z" in txt or "przesyłk" in txt.lower():
            info = btns.nth(i).evaluate('e => ({ tag: e.tagName, text: e.innerText, href: e.getAttribute("href"), testid: e.getAttribute("data-testid") })')
            print(f"Found match: {info}")
    b.close()
