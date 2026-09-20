"""
TEST 16 – Formularz /offer/start/ w trybie WIDOCZNYM (headless=False) + cookies
================================================================================
Cel: znalezc WSZYSTKIE pola formularza wysylki oferty (opis / wycena / dni /
     prawa autorskie / przyciski) i zapisac z nich SCHEMAT do planow.

Sciezka (wg opisu uzytkownika):
    klik w post -> "Dodaj oferte" -> (formularz) -> "Przejdz do podsumowania" -> "Wyslij"

BEZPIECZENSTWO: skrypt NICZEGO nie wypelnia i NIE klika przyciskow wysylki.
Klika tylko link "Dodaj oferte" (to nawigacja do formularza - standardowe otwarcie).
"""
import json
import os
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

TEST_DIR = Path(r"c:\Users\Ksawier\Pictures\Screenshots\useme\lab\test16_formularz_schema")
COOKIES_PATH = TEST_DIR / "cookies.json"
RESULTS_PATH = TEST_DIR / "test16_results.json"
SCHEMA_PATH = TEST_DIR / "form_schema.json"
HTML_PATH = TEST_DIR / "form_html.html"

USEME_BASE = "https://useme.com"
LISTA_URL = "https://useme.com/pl/jobs/category/programowanie-i-it,35/"

ADD_OFFER_TEXTS = ["Dodaj ofertę", "Dodaj ofert", "Dodaj oferte", "Złóż ofertę", "Zloz oferte", "Aplikuj"]


def _is_cf_block(page):
    """Czy strona to Cloudflare challenge ('Just a moment...' / sprawdzanie przegladarki)."""
    try:
        title_lower = page.title().lower()
        if "just a moment" in title_lower or "cierpliwości" in title_lower or "sprawdzanie" in title_lower:
            return True
        for sel in ["#challenge-running", "iframe[src*='cf-chl']", "#challenge-form"]:
            try:
                if page.locator(sel).count() > 0:
                    return True
            except Exception:
                pass
    except Exception:
        pass
    return False


def _czekaj_na_challenge(page, max_czas_s=30, reload_once=False):
    """Czeka az Cloudflare sam rozwiaze challenge. Zwraca True gdy strona dostepna."""
    try:
        start = time.time()
        while time.time() - start < max_czas_s:
            if not _is_cf_block(page):
                return True
            page.wait_for_timeout(2000)
        if reload_once:
            try:
                page.reload(wait_until="domcontentloaded", timeout=30000)
            except Exception:
                pass
            page.wait_for_timeout(3000)
            start = time.time()
            while time.time() - start < max_czas_s:
                if not _is_cf_block(page):
                    return True
                page.wait_for_timeout(2000)
        return not _is_cf_block(page)
    except Exception:
        return not _is_cf_block(page)


def _kliknij_turnstile_checkbox(page):
    """Proba klikniecia checkboxa Turnstile (w widocznej przegladarce czesto wystarczy).
    Zwraca True gdy znaleziono i kliknieto checkbox w iframe Turnstile."""
    try:
        for frame in page.frames:
            src = frame.url or ""
            if "challenges.cloudflare.com" in src or "turnstile" in src:
                for sel in ['input[type="checkbox"]', '.ctp-checkbox-container input[type="checkbox"]',
                            '#challenge-stage input[type="checkbox"]', '[role="checkbox"]']:
                    try:
                        loc = frame.locator(sel).first
                        if loc.count() > 0 and loc.is_visible():
                            box = loc.bounding_box()
                            if box:
                                cx = box["x"] + box["width"] / 2
                                cy = box["y"] + box["height"] / 2
                                page.mouse.move(cx, cy)
                                page.mouse.click(cx, cy)
                                print(f"        [TURNSTILE] kliknieto checkbox: {sel}")
                                return True
                    except Exception:
                        continue
    except Exception as e:
        print(f"        [TURNSTILE] blad: {e}")
    return False


def _akceptuj_baner_cookies(page):
    try:
        loc = page.locator("#cookiescript_accept").first
        if loc.count() > 0 and loc.is_visible():
            loc.click()
            print("    [BANER] kliknieto 'Zaakceptuj cookies' (#cookiescript_accept)")
            page.wait_for_timeout(500)
            return True
    except Exception:
        pass
    return False


def _znajdz_href_dodaj_oferte(page, wyniki):
    """Znajduje link 'Dodaj oferte' na detalu i zwraca jego href (URL formularza)."""
    for tekst in ADD_OFFER_TEXTS:
        for tag in ("a", "button"):
            try:
                loc = page.locator(f"{tag}:has-text('{tekst}')").first
                if loc.count() > 0 and loc.is_visible():
                    href = loc.get_attribute("href") or ""
                    wyniki["link_dodaj_oferte"] = {"tekst": tekst, "href": href, "selektor": f"{tag}:has-text('{tekst}')"}
                    print(f"    [DODAJ OFERTE] znaleziono {tag}: '{tekst}' href={href}")
                    return href
            except Exception:
                continue
    wyniki["link_dodaj_oferte"] = {"znaleziony": False}
    print("    [WARN] nie znaleziono linku 'Dodaj oferte'")
    return None


INSPECT_JS = """
() => {
  const labelFor = {};
  document.querySelectorAll('label').forEach(l => {
    const fr = l.getAttribute('for');
    if (fr) labelFor[fr] = l.innerText.trim();
  });
  const opisPola = (el, index) => {
    const tag = el.tagName.toLowerCase();
    const get = (a) => el.getAttribute(a) || null;
    let label = null;
    const id = get('id');
    if (id && labelFor[id]) label = labelFor[id];
    if (!label) {
      const lab = el.closest('label');
      if (lab) label = lab.innerText.trim();
    }
    if (!label) label = get('aria-label');
    if (!label) {
      const lb = get('aria-labelledby');
      if (lb) { const l = document.getElementById(lb); if (l) label = l.innerText.trim(); }
    }
    if (!label) label = get('title');
    return {
      index, tag,
      name: get('name'), type: get('type'), id,
      placeholder: get('placeholder'), label,
      value: tag === 'button' ? (el.innerText || '').trim().slice(0, 100) : null,
      value_radio: tag === 'input' ? el.value : null,
      checked: tag === 'input' && (el.type === 'radio' || el.type === 'checkbox') ? el.checked : null,
      class: get('class'),
      visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
    };
  };
  const result = {
    liczba_formularzy: document.querySelectorAll('form').length,
    formularze: [],
    wszystkie_pola: [],
    textarea: [], input: [], select: [], radio: [], checkbox: [], submit: [], inne_przyciski: []
  };
  document.querySelectorAll('form').forEach((f, fi) => {
    result.formularze.push({
      index: fi, action: f.getAttribute('action'), method: f.getAttribute('method'),
      id: f.getAttribute('id'), class: f.getAttribute('class'),
      liczba_pol: f.querySelectorAll('input, textarea, select, button').length
    });
  });
  let idx = 0;
  document.querySelectorAll('form input, form textarea, form select, form button').forEach(el => {
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute('type') || '').toLowerCase();
    const info = opisPola(el, idx);
    result.wszystkie_pola.push(info);
    if (tag === 'textarea') result.textarea.push(info);
    else if (tag === 'input') {
      result.input.push(info);
      if (type === 'radio') result.radio.push(info);
      else if (type === 'checkbox') result.checkbox.push(info);
      else if (type === 'submit') result.submit.push(info);
    }
    else if (tag === 'select') result.select.push(info);
    else if (tag === 'button') {
      const t = (el.getAttribute('type') || '').toLowerCase();
      if (t === 'submit') result.submit.push(info);
      else result.inne_przyciski.push(info);
    }
    idx++;
  });
  // teksty przyciskow "Przejdz do podsumowania" / "Wyslij" / prawa autorskie
  result.tekst_strony = {
    decyzja_freelancera: /decyzja\\s+(wykonawcy|freelancera)/i.test(document.body.innerText),
    prawa_autorskie_sekcja: /prawa autorskie/i.test(document.body.innerText),
    przyciski_z_tekstem: Array.from(document.querySelectorAll('button, a')).map(el => (el.innerText || '').trim()).filter(t => t && t.length < 60).slice(0, 60)
  };
  return result;
}
"""


def main():
    wyniki = {
        "test": "16 - formularz wysylki w trybie WIDOCZNYM (headless=False) + cookies",
        "data": datetime.now().isoformat(),
        "stack": {"przegladarka": "chromium", "stealth": True, "cookies": True, "headless": False,
                  "wait_until": "domcontentloaded"},
        "kroki": {},
        "cloudflare": {"blocked_na_liscie": None, "blocked_na_detalu": None, "blocked_na_formularzu": None,
                       "wykryto_widget_turnstile": False},
        "form": None,
    }

    with sync_playwright() as p:
        browser = None
        try:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(viewport={"width": 1920, "height": 1080})
            with open(COOKIES_PATH, "r", encoding="utf-8") as f:
                cd = json.load(f)
            context.add_cookies(cd.get("cookies", cd))
            page = context.new_page()
            Stealth().apply_stealth_sync(page)
            print("[OK] Chromium + stealth + cookies, headless=False")

            # ===== KROK 1: lista ofert =====
            print("\n[1] Wejscie na liste ofert...")
            page.goto(LISTA_URL, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)
            _akceptuj_baner_cookies(page)
            wyniki["kroki"]["lista"] = {"tytul": page.title(), "url": page.url}
            if _is_cf_block(page):
                wyniki["cloudflare"]["blocked_na_liscie"] = True
                print("    >>> Lista zablokowana przez CF (mimo widocznej przegladarki)")
            else:
                wyniki["cloudflare"]["blocked_na_liscie"] = False
                print(f"    OK, tytul: {page.title()}")

            # ===== KROK 2: klik w post (pierwsza oferta) =====
            print("\n[2] Klik w post (pierwsza oferta z listy)...")
            article = page.locator("article.job").first
            link = article.locator("a.job__title-link").first
            if link.count() > 0:
                href = link.get_attribute("href") or ""
                url_detalu = href if href.startswith("http") else USEME_BASE + href
                wyniki["kroki"]["detal"] = {"url": url_detalu}
                print(f"    URL detalu: {url_detalu}")
                link.click(timeout=15000)
                page.wait_for_load_state("domcontentloaded", timeout=30000)
                page.wait_for_timeout(4000)
                _akceptuj_baner_cookies(page)
                wyniki["kroki"]["detal"]["tytul"] = page.title()
                wyniki["kroki"]["detal"]["url_koncowe"] = page.url
                if _is_cf_block(page):
                    wyniki["cloudflare"]["blocked_na_detalu"] = True
                    print("    >>> Detal: CF challenge - czekam...")
                    solved = _czekaj_na_challenge(page, max_czas_s=30, reload_once=True)
                    wyniki["kroki"]["detal"]["cf_rozwiazany"] = solved
                    if not solved:
                        print("    >>> Detal NIE rozwiazal CF - koncze test")
                        wyniki["status"] = "CF_BLOCK_DETAIL"
                        _zapis_wyniki(wyniki)
                        return
                else:
                    wyniki["cloudflare"]["blocked_na_detalu"] = False
                    print(f"    OK, tytul detalu: {page.title()}")
            else:
                print("    [WARN] brak ofert na liscie")
                wyniki["status"] = "BRAK_OFERT"
                _zapis_wyniki(wyniki)
                return

            # ===== KROK 3: przejscie do formularza (URL z linku "Dodaj oferte") =====
            print("\n[3] Przejscie do formularza (URL z linku 'Dodaj oferte')...")
            href_form = _znajdz_href_dodaj_oferte(page, wyniki)
            page_form = page
            if href_form:
                url_form = href_form if href_form.startswith("http") else USEME_BASE + href_form
                print(f"    Goto: {url_form}")
                page_form.goto(url_form, wait_until="domcontentloaded", timeout=45000)
                page_form.wait_for_timeout(5000)
                _akceptuj_baner_cookies(page_form)
                wyniki["form_url_od_linka"] = url_form
            else:
                print("    [FALLBACK] wejscie na https://useme.com/offer/start/ (UWAGA: wg testu to 404!)")
                page_form.goto(USEME_BASE + "/offer/start/", wait_until="domcontentloaded", timeout=45000)
                page_form.wait_for_timeout(5000)
                wyniki["fallback_bezposredni"] = True

            wyniki["kroki"]["formularz"] = {"tytul": page_form.title(), "url": page_form.url}
            print(f"    Formularz - tytul: {page_form.title()}")
            print(f"    Formularz - url: {page_form.url}")

            # ===== KROK 4: Cloudflare / Turnstile na formularzu =====
            if _is_cf_block(page_form):
                wyniki["cloudflare"]["blocked_na_formularzu"] = True
                print("    >>> Formularz: CF challenge - czekam na rozwiazanie...")
                solved = _czekaj_na_challenge(page_form, max_czas_s=35, reload_once=True)
                wyniki["kroki"]["formularz"]["cf_rozwiazany"] = solved
                if not solved:
                    print("    >>> Formularz nadal w CF - proba klikniecia checkboxa Turnstile...")
                    if _kliknij_turnstile_checkbox(page_form):
                        page_form.wait_for_timeout(6000)
                        wyniki["kroki"]["formularz"]["turnstile_checkbox_klikniety"] = True
                        wyniki["kroki"]["formularz"]["cf_rozwiazany_po_kliknieciu"] = not _is_cf_block(page_form)
                if _is_cf_block(page_form):
                    print("    >>> FORMUŁARZ ZABLOKOWANY - nie moge podejrzec pol")
                    wyniki["status"] = "CF_BLOCK_FORM"
                    _zapis_wyniki(wyniki)
                    return
            wyniki["cloudflare"]["blocked_na_formularzu"] = False
            wyniki["cloudflare"]["wykryto_widget_turnstile"] = (
                page_form.locator("div.cf-turnstile, iframe[src*='challenges.cloudflare.com']").count() > 0
            )
            print(f"    Widget Turnstile na stronie: {wyniki['cloudflare']['wykryto_widget_turnstile']}")

            # ===== KROK 5: inspekcja formularza (tylko odczyt) =====
            print("\n[5] Inspekcja formularza (tylko odczyt)...")
            struktura = page_form.evaluate(INSPECT_JS)
            wyniki["form"] = struktura
            wyniki["status"] = "OK_FORM"
            print(f"    Formularze: {struktura['liczba_formularzy']}")
            print(f"    textarea: {len(struktura['textarea'])} | input: {len(struktura['input'])} "
                  f"| radio: {len(struktura['radio'])} | select: {len(struktura['select'])} "
                  f"| submit: {len(struktura['submit'])} | inne: {len(struktura['inne_przyciski'])}")
            print(f"    'decyzja freelancera' na stronie: {struktura['tekst_strony']['decyzja_freelancera']}")
            print(f"    sekcja 'prawa autorskie' na stronie: {struktura['tekst_strony']['prawa_autorskie_sekcja']}")

            # Zrzut HTML (artefakt do analizy selektorow)
            try:
                html = page_form.content()
                HTML_PATH.write_text(html, encoding="utf-8")
                wyniki["zapisano_html"] = str(HTML_PATH)
            except Exception as e:
                wyniki["zapisano_html"] = f"BLAD: {e}"

        except Exception as e:
            wyniki["status"] = "ERROR"
            wyniki["error"] = str(e)
            import traceback
            traceback.print_exc()
        finally:
            if browser:
                browser.close()

    _zapis_wyniki(wyniki)
    if wyniki.get("form"):
        SCHEMA_PATH.write_text(json.dumps(wyniki["form"], indent=2, ensure_ascii=False), encoding="utf-8")
    _podsumowanie(wyniki)


def _zapis_wyniki(wyniki):
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(wyniki, f, indent=2, ensure_ascii=False)
    print(f"\nWyniki zapisane: {RESULTS_PATH}")


def _podsumowanie(wyniki):
    print("\n" + "=" * 60)
    print("PODSUMOWANIE TEST 16")
    print("=" * 60)
    print(f"  Status: {wyniki.get('status')}")
    cf = wyniki.get("cloudflare", {})
    print(f"  CF: lista={cf.get('blocked_na_liscie')} detal={cf.get('blocked_na_detalu')} formularz={cf.get('blocked_na_formularzu')}")
    form = wyniki.get("form")
    if form:
        print(f"  Formularze: {form.get('liczba_formularzy')}")
        print(f"  textarea: {len(form.get('textarea', []))}")
        print(f"  input: {len(form.get('input', []))}")
        print(f"  radio: {len(form.get('radio', []))}")
        print(f"  select: {len(form.get('select', []))}")
        print(f"  submit: {len(form.get('submit', []))}")
        print(f"  'decyzja freelancera': {form.get('tekst_strony', {}).get('decyzja_freelancera')}")
    print("\n  NIE wypelniono i NIE wyslano zadnej oferty (tylko inspekcja DOM).")


if __name__ == "__main__":
    main()
