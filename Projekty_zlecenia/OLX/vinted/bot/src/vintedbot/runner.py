"""Prosty runner konsolowy dla klienta (laik).

Nie pyta o nic technicznego. Klient tylko:
  1. login — zaloguj się w oknie przeglądarki (raz)
  2. start — bot łapie iPhone wg filtrów z pliku filtry.json

Filtry (modele iPhone, widełki cenowe, blacklist tytułów) są w pliku
`filtry.json` obok bota. Klient edytuje ten plik notatnikiem — nie rusza kodu.
"""

import json
import re
from pathlib import Path

from .config import wczytaj_cookies, csrf_z_cookies
from .models import Filtry, KonfiguracjaKonta
from .session_state import SessionState

DEFAULT_PROFILE = "profil_vinted2"
DEFAULT_COOKIES = "cookies_vinted2.json"
FILTRY_PATH = Path(__file__).resolve().parent.parent.parent / "filtry.json"


def _wczytaj_filtry() -> dict:
    """Czyta filtry.json; zwraca dict {modele, cena_max_globalna, blacklist_titul}."""
    try:
        data = json.loads(FILTRY_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"UWAGA: brak pliku {FILTRY_PATH} — używam pustych filtrów.")
        return {"modele": [], "cena_max_globalna": 2000, "blacklist_titul": []}
    except Exception as exc:
        print(f"UWAGA: nie udało się wczytać {FILTRY_PATH}: {exc}")
        return {"modele": [], "cena_max_globalna": 2000, "blacklist_titul": []}

    modele = []
    for m in data.get("modele", []):
        modele.append((m.get("wzorzec", ""), m.get("cena_min", 0), m.get("cena_max", 0)))
    blacklist = list(data.get("blacklist_titul", []))
    cena_max = data.get("cena_max_globalna", 2000)
    return {"modele": modele, "cena_max_globalna": cena_max, "blacklist_titul": blacklist}


def czy_pasuje_iphone(title: str, cena: float, filtry: dict | None = None) -> bool:
    """Zwraca True, jeśli oferta pasuje do widełek z filtry.json (tytuł + cena)."""
    if filtry is None:
        filtry = _wczytaj_filtry()
    t = (title or "").lower()
    for w in filtry.get("blacklist_titul", []):
        if w in t:
            return False
    for pattern, lo, hi in filtry.get("modele", []):
        if pattern and re.search(pattern, t):
            return lo <= cena <= hi
    return False


class Runner:
    """Stan sesji + proste menu po polsku, dla laika."""

    def __init__(self) -> None:
        self.state = SessionState()
        self.profil = DEFAULT_PROFILE
        self.cookies_path = DEFAULT_COOKIES

    # ---- logowanie ----

    def _ensure_camoufox(self) -> None:
        """Instaluje Camoufox przy pierwszym uruchomieniu, jeśli brakuje."""
        try:
            from camoufox.pkgman import installed_verstr
            installed_verstr()
            return
        except Exception:
            pass
        print("Pierwsze uruchomienie — pobieram przeglądarkę (chwilę to potrwa)...")
        import subprocess
        import sys
        subprocess.run([sys.executable, "-m", "camoufox", "fetch"], check=False)

    def cmd_login(self) -> None:
        """Zaloguj przez Camoufox (okno) i zapisz cookies.

        Nie używamy auto-detekcji RefreshLoop — ona najpierw robi cichą próbę
        headless (90 s) i opiera się na JS w przeglądarce, co u laika wygląda
        jakby "nic się nie działo". Zamiast tego: otwórz okno, klient loguje
        się ręcznie, wraca do konsoli i naciska Enter — my dopiero wtedy
        pobieramy cookies i sprawdzamy zwykłym HTTP.
        """
        self._ensure_camoufox()
        print()
        print("Otwieram okno przeglądarki...", flush=True)
        from camoufox import Camoufox
        from .refresh import LOGIN_PAGE_URL, LOGIN_URL, WEBGL_CONFIG, _czy_zalogowany

        try:
            with Camoufox(
                persistent_context=True,
                headless=False,
                user_data_dir=self.profil,
                os="windows",
                fingerprint_preset=True,
                humanize=False,
                webgl_config=WEBGL_CONFIG,
            ) as ctx:
                # JEDNO okno: używamy istniejącej karty persistent contextu.
                # Dokładanie drugiej karty kradło focus i uniemożliwiało wpisywanie.
                pages = getattr(ctx, "pages", None) or []
                page = pages[0] if pages else ctx.new_page()
                page.goto(LOGIN_PAGE_URL, wait_until="domcontentloaded", timeout=60000)
                # Poczekaj aż ciężki JS (React + DataDome) się wyrenderuje,
                # żeby przycisk "Zaloguj przez Google" był klikalny, a nie zamrożony.
                try:
                    page.wait_for_timeout(4000)
                except Exception:
                    pass
                print()
                print("Zaloguj się w oknie przeglądarki (tak jak normalnie na Vinted).", flush=True)
                print("(pisz w oknie przeglądarki, NIE w tym czarnym oknie)", flush=True)
                input("Jak już będziesz zalogowany, wróć TU i naciśnij Enter...")
                # Po zalogowaniu przez Google Vinted robi kilka przekierowań. NIE
                # dotykamy strony od razu (page.evaluate w trakcie nawigacji = błąd
                # "Execution context was destroyed"). Autorytatywny sygnał zalogowania
                # to obecność cookie access_token_web — ustawia go serwer Vinted po
                # udanym logowaniu, więc DataDome tu nie miesza.
                try:
                    page.wait_for_timeout(3000)
                except Exception:
                    pass
                raw = ctx.cookies()
                cookies = {c.get("name", ""): c.get("value", "") for c in raw if c.get("name")}

                # login/user_id dobieramy z /users/current wewnątrz przeglądarki, ale
                # z ponawianiem (redirect po Google może niszczyć kontekst). Nie są one
                # krytyczne: login to kosmetyka, user_id ma fallback w checkoucie.
                login, uid = None, None
                if cookies.get("access_token_web"):
                    for _ in range(5):
                        try:
                            login, uid = _czy_zalogowany(page)
                            if login:
                                break
                        except Exception:
                            pass
                        try:
                            page.wait_for_timeout(1500)
                        except Exception:
                            pass

                self.state.set_cookies(cookies, login=login, user_id=uid)
        except Exception as exc:
            print(f"Problem z przeglądarką: {exc}")
            return

        if not self.state.cookies.get("access_token_web"):
            print("Nie wykryłem zalogowania. Spróbuj jeszcze raz (wpisz login).")
            return
        try:
            Path(self.cookies_path).write_text(
                json.dumps(self.state.cookies, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print("Logowanie zapisane.")
        except Exception as exc:
            print(f"Uwaga: nie zapisałem logowania: {exc}")
        print(f"Zalogowano: {self.state.login or '(token OK)'}")

    # ---- start ----

    def cmd_start(self) -> None:
        """Uruchom autobuy na filtrach z filtry.json."""
        if not self._ensure_cookies():
            return

        filtry = _wczytaj_filtry()
        modele = filtry.get("modele", [])
        if not modele:
            print("Brak modeli w filtry.json. Uzupełnij plik i spróbuj ponownie.")
            return
        cena_max = float(filtry.get("cena_max_globalna", 2000))

        print()
        print("Bot będzie szukał iPhone'ów wg filtrów z filtry.json:")
        print(f"  {len(modele)} modeli, cena maksymalna w katalogu: {cena_max} zł")
        print("  Uszkodzone biorę, etui/szkła/icloud odrzucam (blacklist w filtry.json).")
        print()
        odp = input("Zacząć kupować od razu, czy najpierw tylko pokazywać trafienia? (kupuj / podglad): ").strip().lower()
        kupuj = odp in ("kupuj", "k", "tak", "t", "kup")
        if kupuj:
            print("OK, bot będzie kupował. Jeśli oferta wymaga 3DS, dostaniesz link do potwierdzenia.")
            print("Zatrzymasz klawiszem Ctrl+C.")
        else:
            print("OK, tryb podglądu — bot tylko pokaże trafienia, nic nie kupi.")

        from .checkout import zrealizuj_zakup, prewarm_sesje
        from .detection import monitoruj, odswiez_token

        konto = self._konto()
        try:
            prewarm_sesje(konto)
        except Exception:
            pass

        # L1: odśwież access_token_web przed pętlą, żeby token nie wygasł w trakcie
        # zakupu (checkout sam nie odświeża tokenu). Błąd odświeżenia nie blokuje startu.
        try:
            from .refresh import _token_expires_in
            exp = _token_expires_in(self.state.cookies)
            if exp is None or exp < 120:
                odswiez_token(self.state.cookies)
                print("[vintedbot] token odświeżony przed startem.", flush=True)
        except Exception:
            pass

        def on_nowe(nowe):
            for o in nowe:
                cena = o.cena if hasattr(o, "cena") else 0.0
                if not czy_pasuje_iphone(o.title, cena, filtry):
                    continue
                if o.seller_id is None:
                    print(f"[trafienie] {o.title} — {cena} zł (brak sprzedawcy, pomijam)")
                    continue
                print(f"[trafienie] {o.title} — {cena} zł")
                if not kupuj:
                    continue
                try:
                    w = zrealizuj_zakup(o.id, o.seller_id, konto, proba_payment=True)
                    print(f"[zakup] {o.title}: rezerwacja OK")
                    if w.redirect_url:
                        print(f"[3DS] potwierdź tutaj: {w.redirect_url}")
                except Exception as exc:
                    print(f"[zakup] nie udało się: {exc}")

        # Szukamy szeroko "iphone" i filtrujemy po tytule+cenie lokalnie.
        f = Filtry(search_text="iphone", price_from=0.0, price_to=cena_max)
        try:
            monitoruj(f, interwal=1.0, callback=on_nowe, cookies=self.state.cookies)
        except KeyboardInterrupt:
            print("\nZatrzymano.")

    # ---- pomocnicze ----

    def _sprawdz_cookies_na_starcie(self) -> None:
        """Przy starcie: załaduj cookies z pliku i sprawdź ważność lokalnie.

        Nie używamy is_ready() (curl_cffi) — DataDome może zwrócić 403 na
        poprawnie zalogowaną sesję. Zamiast tego czytamy JWT access_token_web
        i jego datę ważności lokalnie. Klient od razu widzi, czy musi się logować.
        """
        if self.state.cookies and self.state.cookies.get("access_token_web"):
            return
        try:
            self.state.cookies = wczytaj_cookies(self.cookies_path)
        except FileNotFoundError:
            self.state.cookies = {}
            return
        except Exception as exc:
            print(f"Problem z wczytaniem logowania: {exc}")
            self.state.cookies = {}
            return

        if not self.state.cookies.get("access_token_web"):
            return
        try:
            from .refresh import _token_expires_in
            exp = _token_expires_in(self.state.cookies)
            if exp is not None and exp <= 0:
                print("UWAGA: zapisane logowanie wygasło — wpisz 'login', żeby się zalogować ponownie.")
        except Exception:
            pass

    def _ensure_cookies(self) -> bool:
        """Załaduj cookies; jeśli brak tokenu lub wygasł, każ się zalogować.

        Uwaga: NIE używamy is_ready() (curl_cffi) — DataDome potrafi dać 403
        na poprawnie zalogowaną sesję i fałszywie zgłosić "wygasło". Zamiast tego
        sprawdzamy obecność access_token_web i jego datę ważności lokalnie z JWT.
        """
        if self.state.cookies and self.state.cookies.get("access_token_web"):
            return True
        try:
            self.state.cookies = wczytaj_cookies(self.cookies_path)
        except FileNotFoundError:
            print("Najpierw się zaloguj — wpisz 'login'.")
            return False
        except Exception as exc:
            print(f"Problem z logowaniem: {exc}")
            return False

        if not self.state.cookies.get("access_token_web"):
            print("Najpierw się zaloguj — wpisz 'login'.")
            return False
        try:
            from .refresh import _token_expires_in
            exp = _token_expires_in(self.state.cookies)
            if exp is not None and exp <= 0:
                print("Logowanie wygasło. Wpisz 'login' i zaloguj się ponownie.")
                return False
        except Exception:
            pass
        return True

    def _konto(self) -> KonfiguracjaKonta:
        konto = KonfiguracjaKonta(cookies=self.state.cookies)
        csrf = csrf_z_cookies(self.state.cookies)
        if csrf:
            konto = konto.model_copy(update={"csrf": csrf})
        if self.state.user_id is not None:
            konto = konto.model_copy(update={"user_id": int(self.state.user_id)})
        return konto

    def run(self) -> None:
        # Licencja offline (Ed25519) — jak wygasła, bot nie wystartuje.
        from .licencja import sprawdz_licencje_na_starcie

        sprawdz_licencje_na_starcie()
        print()
        print("=== BOT VINTED ===")
        print()
        # Sprawdź cookies od razu przy starcie, żeby klient od razu wiedział,
        # czy jest zalogowany, czy musi wpisać login.
        self._sprawdz_cookies_na_starcie()
        if self.state.cookies.get("access_token_web"):
            print("Status: zalogowany (session zapisana).")
            print()
            print("Masz 1 krok do startu:")
            print("  1) wpisz  start   — bot zacznie łapać iPhone'y")
        else:
            print("Status: NIE zalogowany.")
            print()
            print("Masz 2 kroki na start:")
            print("  1) wpisz  login   — zalogujesz się w oknie przeglądarki")
            print("  2) wpisz  start   — bot zacznie łapać iPhone'y")
        print()
        print("Inne: help (pomoc), exit (wyjdź)")
        while True:
            try:
                cmd = input("\nco robimy? > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nDo widzenia.")
                break
            if cmd in ("exit", "quit", "q", "wyjdz", "wyjdź"):
                break
            elif cmd in ("login", "zaloguj", "1"):
                self.cmd_login()
            elif cmd in ("start", "2", "3"):
                self.cmd_start()
            elif cmd == "help":
                print("login  — zaloguj się (raz)")
                print("start  — bot łapie iPhone'y wg Twoich widełek")
                print("exit   — zamknij bota")
            else:
                print("Nie rozumiem. Wpisz 'help', żeby zobaczyć co umiem.")


def main() -> None:
    Runner().run()


if __name__ == "__main__":
    main()