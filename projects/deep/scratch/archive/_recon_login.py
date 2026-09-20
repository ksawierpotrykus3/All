"""Tymczasowy rekonesans strony logowania DeepSeek - zrzuca strukture formularza."""
import sys, time, json
from pathlib import Path
from DrissionPage import ChromiumPage, ChromiumOptions

root_dir = Path(__file__).parent
slot = int(sys.argv[1]) if len(sys.argv) > 1 else 2
data_dir = root_dir / ".chrome_slot" / f"slot_{slot}"
data_dir.mkdir(parents=True, exist_ok=True)

opt = ChromiumOptions()
opt.set_user_data_path(str(data_dir))
opt.set_argument("--no-first-run")
opt.set_argument("--no-default-browser-check")
opt.set_argument("--disable-blink-features=AutomationControlled")
opt.set_argument("--disable-infobars")
opt.set_argument("--window-size=1280,900")
opt.auto_port()

page = ChromiumPage(opt)
try:
    page.get("https://chat.deepseek.com/sign_in")
    print("URL:", page.url)
    print("TITLE:", page.title)

    # czekaj az WAF/page sie ustabilizuje
    for _ in range(20):
        time.sleep(1)
        try:
            if page.ele("tag:input", timeout=0.5):
                break
        except Exception:
            pass

    print("URL po czekaniu:", page.url)
    print("TITLE po czekaniu:", page.title)

    out = []
    out.append(f"URL: {page.url}")
    out.append(f"TITLE: {page.title}")
    out.append("")

    out.append("=== INPUTS ===")
    for el in page.eles("tag:input"):
        try:
            attrs = el.attrs
            info = {k: attrs.get(k) for k in ("type", "name", "id", "placeholder", "class", "autocomplete", "maxlength") if k in attrs}
            out.append(f"  {info} | visible={el.states.is_displayed}")
        except Exception as e:
            out.append(f"  err {e}")

    out.append("")
    out.append("=== BUTTONS ===")
    for el in page.eles("tag:button"):
        try:
            out.append(f"  text={el.text!r} class={el.attrs.get('class')} type={el.attrs.get('type')} visible={el.states.is_displayed}")
        except Exception as e:
            out.append(f"  err {e}")

    out.append("")
    out.append("=== DIV role=button / clickable ===")
    for el in page.eles("css:div[role=button]"):
        try:
            out.append(f"  text={el.text!r} class={el.attrs.get('class')}")
        except Exception:
            pass

    out.append("")
    out.append("=== LABELS / TEXT NODES ===")
    for el in page.eles("tag:label"):
        try:
            out.append(f"  label={el.text!r}")
        except Exception:
            pass

    out.append("")
    out.append("=== ALL VISIBLE TEXT (body) ===")
    try:
        body_txt = page.ele("tag:body").text
        out.append(body_txt[:3000])
    except Exception as e:
        out.append(f"err {e}")

    out.append("")
    out.append("=== localStorage keys ===")
    try:
        out.append(str(page.run_js("return Object.keys(localStorage)")))
    except Exception as e:
        out.append(f"err {e}")

    dump = root_dir / "data" / "login_recon.txt"
    dump.write_text("\n".join(out), encoding="utf-8")
    print("ZAPISANO:", dump)

    # zrzut HTML formularza
    try:
        html = page.html
        (root_dir / "data" / "login_recon.html").write_text(html, encoding="utf-8")
        print("ZAPISANO HTML, dlugosc:", len(html))
    except Exception as e:
        print("html err", e)

    print("\n--- PODSUMOWANIE ---")
    print("\n".join(out[:60]))
finally:
    pass  # zostawiamy okno otwarte do inspekcji
