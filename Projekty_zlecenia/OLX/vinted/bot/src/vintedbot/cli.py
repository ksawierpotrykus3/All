import json

import click

from . import evidence
from .config import wczytaj_cookies, csrf_z_cookies
from .checkout import zrealizuj_zakup, prewarm_sesje, pobierz_sesje
from .detection import pobierz_oferty, monitoruj
from .measurement import LatencyRecorder
from .models import Filtry, KonfiguracjaKonta


@click.group()
def cli():
    """Vinted bot — monitoring i rezerwacja (curl_cffi)."""


@cli.command()
@click.option("--brand", multiple=True, type=int, help="ID marki (powtarzalny)")
@click.option("--size", multiple=True, type=int, help="ID rozmiaru (powtarzalny)")
@click.option("--status", multiple=True, type=int, help="ID stanu (powtarzalny)")
@click.option("--price-from", default=None, type=float, help="Cena od")
@click.option("--price-to", default=None, type=float, help="Cena do")
@click.option("--search", default=None, help="Słowa kluczowe")
@click.option("--limit", default=10, type=int, help="Ile ofert pobrać")
@click.option("--cookies", default=None, type=click.Path(exists=True), help="Ścieżka do pliku cookies (JSON lub Netscape)")
def monitor(brand, size, status, price_from, price_to, search, limit, cookies):
    """Pobierz i wypisz oferty pasujące do filtrów."""
    f = Filtry(
        brand_ids=list(brand),
        size_ids=list(size),
        status_ids=list(status),
        price_from=price_from,
        price_to=price_to,
        search_text=search,
    )
    ck = wczytaj_cookies(cookies) if cookies else None
    oferty = pobierz_oferty(f, limit=limit, cookies=ck)
    for o in oferty:
        click.echo(f"{o.id}\t{o.title}\t{o.cena}")


@cli.command()
@click.option("--brand", multiple=True, type=int)
@click.option("--search", default=None)
@click.option("--max-iter", default=None, type=int)
@click.option("--no-checkout", is_flag=True, help="Nie rezerwuj — tylko wykryj")
@click.option("--cookies", default=None, type=click.Path(exists=True), help="Cookies (JSON lub Netscape)")
@click.option("--payment", is_flag=True, help="Po rezerwacji spróbuj dojść do próby payment")
@click.option("--timing/--no-timing", default=True, help="Zapisuj czasy kroków (ms) z timestampem (domyślnie włączone)")
@click.option("--screenshot/--no-screenshot", default=False, help="Screenshot checkoutu/bramki przez Camoufox (koszt ~8-15 s; domyślnie WYŁĄCZONY, wykonuje się w tle)")
@click.option("--profil", default=None, type=click.Path(exists=False), help="Profil Camoufox do screena (opcjonalny)")
@click.option("--refresh-cookies", is_flag=True, help="Pobierz świeże cookies Camoufoxem z --profil (ignoruje --cookies)")
@click.option("--dry-run", is_flag=True, help="Wykrywaj oferty, ale NIE rezerwuj (test bezpieczny)")
def autocop(brand, search, max_iter, no_checkout, cookies, payment, timing, screenshot, profil, refresh_cookies, dry_run):
    """Monitoruj i (opcjonalnie) rezerwuj + próbuj zapłacić (curl_cffi)."""
    f = Filtry(brand_ids=list(brand), search_text=search)
    if refresh_cookies and profil:
        from .refresh import pobierz_swieze_cookies
        ck = pobierz_swieze_cookies(profil)
        click.echo(f"SWIEZE COOKIES z profilu: {len(ck)} szt.")
    else:
        ck = wczytaj_cookies(cookies) if cookies else {}
    konto = KonfiguracjaKonta(cookies=ck)
    csrf = csrf_z_cookies(ck)
    if csrf:
        konto = konto.model_copy(update={"csrf": csrf})
    if not (no_checkout or dry_run):
        prewarm_sesje(konto)

    def on_nowe(nowe):
        for o in nowe:
            click.echo(f"NOWA: {o.id} {o.title} {o.cena}")
            if no_checkout or dry_run:
                if dry_run:
                    click.echo(f"(dry-run: pomijam rezerwację {o.id})")
                continue
            if o.seller_id is None:
                click.echo("(pominięto — brak seller_id)")
                continue
            w = zrealizuj_zakup(o.id, o.seller_id, konto, proba_payment=payment, profil=profil)
            if w.checkout_id:
                click.echo(f"REZERWACJA: checkout={w.checkout_id} build={w.status_build}")
            if payment:
                click.echo(f"PAYMENT: status={w.status_payment} redirect={w.redirect_url}")
            if timing or screenshot:
                # O1: async — raport timingów od razu, screenshot Camoufox w tle
                # (nie blokuje pętli monitorującej kolejnych ofert).
                paths = evidence.zapisz_dowody_async(
                    w, prefix=f"autocop_{o.id}", timings=timing, screenshot=screenshot,
                    payment=payment, profil=profil,
                )
                for kind, p in paths.items():
                    click.echo(f"DOWÓD [{kind}]: {p}")

    monitoruj(f, interwal=1.0, callback=on_nowe, max_iter=max_iter, cookies=ck)


@cli.command()
@click.option("--brand", multiple=True, type=int)
@click.option("--search", default=None)
@click.option("--max-iter", default=5, type=int)
@click.option("--cookies", default=None, type=click.Path(exists=True))
@click.option("--out", default=None, type=click.Path(dir_okay=False), help="Ścieżka zapisu raportu JSON")
@click.option("--timing/--no-timing", default=True, help="Zapisuj raport timingów (ms) z timestampem (domyślnie włączone)")
def bench(brand, search, max_iter, cookies, out, timing):
    """Benchmark detekcji: mierzy RTT i latencję wewnętrzną. Wypisuje raport JSON."""
    f = Filtry(brand_ids=list(brand), search_text=search)
    ck = wczytaj_cookies(cookies) if cookies else None
    rtt = LatencyRecorder()
    wewn = LatencyRecorder()
    # O2: sesja keep-alive — spójnie z daemonem (pomiar miarodajny dla produkcji).
    session = None
    if ck:
        try:
            session = pobierz_sesje(KonfiguracjaKonta(cookies=ck), "detekcja")
        except Exception:
            session = None

    def _cb(nowe):
        pass

    monitoruj(f, interwal=0.0, callback=_cb, max_iter=max_iter, cookies=ck,
              session=session, recorder=rtt, recorder_wewn=wewn)
    report = {"rtt": rtt.to_dict(), "wewn": wewn.to_dict()}
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
    click.echo(json.dumps(report, ensure_ascii=False))
    if timing:
        p = evidence.zapisz_raport_timingow(report, prefix="bench")
        if p:
            click.echo(f"DOWÓD [timing_report]: {p}")


@cli.command()
@click.option("--cookies", required=True, type=click.Path(exists=True), help="Ścieżka do pliku cookies (JSON lub Netscape)")
@click.option("--co-ile", default=1800, type=int, help="Odstęp między odświeżeniami w sekundach (domyślnie 1800 = 30 min)")
def keepalive(cookies, co_ile):
    """Cyklicznie odświeża token sesji, żeby nie wygasła (edge case E1)."""
    from .detection import utrzymuj_sesje

    ck = wczytaj_cookies(cookies)
    click.echo(f"Utrzymywanie sesji co {co_ile}s. Ctrl+C aby zatrzymać.")
    utrzymuj_sesje(ck, co_ile_s=float(co_ile))


@cli.command()
@click.option("--brand", multiple=True, type=int, help="ID marki (powtarzalny)")
@click.option("--search", default=None, help="Słowa kluczowe")
@click.option("--cookies", "cookies_paths", multiple=True, required=True,
              type=click.Path(exists=True), help="Plik cookies (powtarzalny; 1 na konto)")
@click.option("--profil", "profile", multiple=True, required=True,
              type=click.Path(exists=False), help="Katalog profilu Camoufox (powtarzalny; 1 na konto)")
@click.option("--interval", default=4, type=int, help="Interwał refresh sesji (minuty)")
@click.option("--payment", is_flag=True, help="Próbuj dojść do kroku payment po rezerwacji")
@click.option("--timing/--no-timing", default=True, help="Zapisuj czasy kroków (ms) z timestampem (domyślnie włączone)")
@click.option("--screenshot/--no-screenshot", default=False, help="Screenshot checkoutu/bramki przez Camoufox (koszt ~8-15 s; domyślnie WYŁĄCZONY, wykonuje się w tle)")
@click.option("--dry-run", is_flag=True, help="Wykrywaj oferty, ale NIE rezerwuj (test bezpieczny)")
def daemon(brand, search, cookies_paths, profile, interval, payment, timing, screenshot, dry_run):
    """Uruchom daemon: podtrzymuj sesję i automatycznie rezerwuj pasujące oferty (multi-konto)."""
    from .daemon import run_daemon_multi
    from .models import Filtry

    if len(cookies_paths) != len(profile):
        raise click.UsageError("Liczba --cookies musi być równa liczbie --profil (1 plik cookies na 1 profil).")

    f = Filtry(brand_ids=list(brand), search_text=search)
    konta = [{"cookies_path": c, "profil": p} for c, p in zip(cookies_paths, profile)]
    run_daemon_multi(konta, filtry=f, proba_payment=payment,
                     refresh_interval_min=interval,
                     timing=timing, screenshot=screenshot, dry_run=dry_run)


@cli.command("add-card")
@click.option("--number", required=True, help="Numer karty płatniczej (16 cyfr)")
@click.option("--exp-month", required=True, help="Miesiąc ważności (np. 12)")
@click.option("--exp-year", required=True, help="Rok ważności (np. 2026)")
@click.option("--cvc", required=True, help="Kod bezpieczeństwa CVC/CVV")
@click.option("--cookies", required=True, type=click.Path(exists=True), help="Plik cookies")
@click.option("--single-use", is_flag=True, help="Karta jednorazowa")
def add_card(number, exp_month, exp_year, cvc, cookies, single_use):
    """Zarejestruj nową kartę płatniczą przez Adyen CSE."""
    from .card_manager import zarejestruj_karte
    ck = wczytaj_cookies(cookies)
    konto = KonfiguracjaKonta(cookies=ck)
    csrf = csrf_z_cookies(ck)
    if csrf:
        konto = konto.model_copy(update={"csrf": csrf})
    
    karta = {
        "number": number.replace(" ", "").replace("-", ""),
        "expiryMonth": str(exp_month).zfill(2),
        "expiryYear": str(exp_year),
        "cvc": str(cvc),
    }
    click.echo("Szyfrowanie karty przez Adyen CSE i rejestracja w API Vinted...")
    try:
        res = zarejestruj_karte(karta, konto, single_use=single_use)
        click.echo(f"SUKCES: Zarejestrowano kartę. Odpowiedź: {json.dumps(res, ensure_ascii=False)}")
    except Exception as e:
        click.echo(f"BŁĄD rejestracji karty: {e}")


@cli.command("cards")
@click.option("--cookies", required=True, type=click.Path(exists=True), help="Plik cookies")
def list_cards(cookies):
    """Wyświetl listę zarejestrowanych kart płatniczych."""
    from .card_manager import pobierz_zapisane_karty
    ck = wczytaj_cookies(cookies)
    konto = KonfiguracjaKonta(cookies=ck)
    csrf = csrf_z_cookies(ck)
    if csrf:
        konto = konto.model_copy(update={"csrf": csrf})
    try:
        karty = pobierz_zapisane_karty(konto)
        click.echo(f"Zapisane karty ({len(karty)}):")
        for c in karty:
            click.echo(f"ID: {c.get('id')} | {c.get('brand')} **** {c.get('last4')} | domyślna: {c.get('is_default')}")
    except Exception as e:
        click.echo(f"BŁĄD pobierania kart: {e}")


@cli.command("delete-card")
@click.option("--id", "card_id", required=True, help="ID karty do usunięcia")
@click.option("--cookies", required=True, type=click.Path(exists=True), help="Plik cookies")
def delete_card_cmd(card_id, cookies):
    """Usuń kartę płatniczą z konta."""
    from .card_manager import usun_karte
    ck = wczytaj_cookies(cookies)
    konto = KonfiguracjaKonta(cookies=ck)
    csrf = csrf_z_cookies(ck)
    if csrf:
        konto = konto.model_copy(update={"csrf": csrf})
    try:
        ok = usun_karte(card_id, konto)
        if ok:
            click.echo(f"Usunięto kartę {card_id}.")
        else:
            click.echo(f"Nie udało się usunąć karty {card_id}.")
    except Exception as e:
        click.echo(f"BŁĄD usuwania karty: {e}")


if __name__ == "__main__":
    cli()


