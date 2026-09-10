import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bot" / "src"))

from vintedbot.refresh import RefreshLoop
from vintedbot.session_state import SessionState
from vintedbot.config import csrf_z_cookies

PROFIL = str(ROOT / "vinted" / "testy_camoufox" / "implementation" / "browser-profiles" / "profil_firefox_135")
state = SessionState()
loop = RefreshLoop(PROFIL)

print("==================================================")
print("=== LOGOWANIE DO VINTED (Camoufox Headful)     ===")
print("==================================================")
print("Otwieranie okna przegladarki...")
print("Zaloguj sie na swoje konto Vinted w otwartym oknie.")
print("Czekam na logowanie...")

ok = loop._try_refresh(state, headless=False)

if ok:
    cookies = state.cookies
    csrf = csrf_z_cookies(cookies)
    print("\n" + "=" * 50)
    print("✅ SUKCES! Zalogowano jako:", getattr(state, "login", "?"))
    print("   anon_id:", cookies.get("anon_id"))
    print("   csrf:", csrf)
    print("=" * 50)
else:
    print("\n❌ Blad: Nie udalo sie zalogowac (timeout lub zamknieto okno).")

input("\nNacisnij ENTER aby zakonczyc...")
