import json
from pathlib import Path
from playwright.sync_api import sync_playwright

PROFILE_DIR = Path("profiles/olx_profile")

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        str(PROFILE_DIR),
        headless=True,
        locale="pl-PL",
        viewport={"width": 1400, "height": 900},
        args=["--disable-blink-features=AutomationControlled"],
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("https://www.olx.pl/buy-options/1018987579", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    page.locator("[data-testid='buy-option-with-delivery']").first.click()
    page.wait_for_timeout(600)
    page.locator("[data-testid='buy-options-continue']").first.click()
    page.wait_for_timeout(4500)

    # Otwórz modal wyboru Paczkomatu
    page.locator("[data-testid='select-locker']").first.click()
    page.wait_for_timeout(3500)

    # Zrzut modalu
    page.screenshot(path="gemini/dane/paczkomat_modal_live.png")

    # Wyciągnij elementy z prawej kolumny (gdzie są adresy)
    items = page.eval_on_selector_all(
        "*",
        """els => els.map(e => ({
            tag: e.tagName,
            testId: e.getAttribute('data-testid'),
            className: typeof e.className === 'string' ? e.className : '',
            text: (e.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 80),
            role: e.getAttribute('role'),
            id: e.id || ''
        })).filter(x => x.text.includes('Południowa') || x.text.includes('Parzęczew') || x.text.includes('Zachodnia') || (x.testId && x.testId.includes('point')) || (x.testId && x.testId.includes('locker')) || (x.testId && x.testId.includes('pickup')) || (x.testId && x.testId.includes('service')) || (x.testId && x.testId.includes('item')) || (x.testId && x.testId.includes('list')) || (x.testId && x.testId.includes('select')) || (x.testId && x.testId.includes('choose')) )"""
    )
    Path("gemini/dane/paczkomat_dom_dump.json").write_text(
        json.dumps(items[:50], indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Znaleziono {len(items)} elementów.")
    for it in items[:25]:
        print(f"<{it['tag']}> id='{it['id']}' testId='{it['testId']}' class='{it['className'][:40]}' text='{it['text'][:40]}'")
    ctx.close()
