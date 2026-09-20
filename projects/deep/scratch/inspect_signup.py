import time
from pathlib import Path
from DrissionPage import ChromiumPage, ChromiumOptions

data_dir = Path(__file__).parent / ".test_deepseek_profile"
data_dir.mkdir(parents=True, exist_ok=True)

opt = ChromiumOptions()
opt.set_user_data_path(str(data_dir))
opt.set_argument("--no-first-run")
opt.set_argument("--no-default-browser-check")
opt.set_argument("--disable-blink-features=AutomationControlled")
opt.set_argument("--window-size=1280,900")
opt.auto_port()

page = ChromiumPage(opt)
try:
    print("[1] Otwieram https://chat.deepseek.com/sign_up...", flush=True)
    page.get("https://chat.deepseek.com/sign_up")
    time.sleep(5)
    
    print("URL:", page.url, flush=True)
    print("Title:", page.title, flush=True)
    
    inputs = page.eles("tag:input")
    print(f"\nZnaleziono {len(inputs)} pol input:")
    for inp in inputs:
        print("  input:", inp.attrs, "visible=", inp.states.is_displayed, flush=True)
        
    buttons = page.eles("tag:button")
    print(f"\nZnaleziono {len(buttons)} button:")
    for b in buttons:
        print(f"  button: text={b.text!r} class={b.attrs.get('class')}", flush=True)
        
    div_btns = page.eles("css:div[role=button]")
    print(f"\nZnaleziono {len(div_btns)} div[role=button]:")
    for db in div_btns:
        print(f"  div[role=button]: text={db.text!r} class={db.attrs.get('class')}", flush=True)
        
    body_text = page.ele("tag:body").text if page.ele("tag:body") else ""
    lines = [l.strip() for l in body_text.splitlines() if l.strip()]
    print("\nTekst strony:")
    for l in lines[:30]:
        print("  |", l.encode('ascii', 'replace').decode('ascii'), flush=True)
finally:
    try:
        page.quit()
    except Exception:
        pass
