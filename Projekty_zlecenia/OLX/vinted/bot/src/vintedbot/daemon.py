"""Daemon: spina pętlę refresh (Camoufox) i pętlę zakupową (curl_cffi).

Architektura wydajnościowa:
- Wątek POLL: tylko odpytywanie katalogu przez współdzieloną sesję keep-alive.
  NIGDY nie wykonuje checkoutu — nowe oferty wrzuca na kolejkę.
- Wątek WORKER: konsumuje kolejkę i wykonuje checkout. Dzięki temu polling
  płynie nieprzerwanie podczas zakupu (O6) — kops.gg robi to samo (Parallel).
- Screenshot (Camoufox ~8-15 s) idzie w wątku tła (O1), nie blokuje workera.
"""
import queue
import signal
import threading

from . import evidence
from .checkout import zrealizuj_zakup, prewarm_sesje, pobierz_sesje
from .models import Filtry, KonfiguracjaKonta
from .refresh import RefreshLoop
from .session_state import SessionState, SessionStatus

# Interwał odpytywania katalogu (s). Rate-limit Vinted ~0.83 req/s -> ~1.2 s
# bezpieczny okres; 1.0 s to agresywny, ale tolerowany sufit (AGENTS.md).
POLL_INTERVAL = 1.0

# P1: limit ofert na poll. [UDOWODNIONE rtt_per_page.json] RTT katalogu rośnie z
# per_page: 5->360 ms, 10->515 ms, 24->640 ms, 48->1047 ms, 96->1188 ms.
# order=newest_first gwarantuje, że najnowsze oferty są zawsze na początku,
# więc limit=5 w zupełności wystarcza do detekcji i skraca pętlę ~30% (-155 ms/poll).
POLL_LIMIT = 5


class PurchaseLoop:
    def __init__(self, state: SessionState, filtry: Filtry, proba_payment: bool,
                 timing: bool = True, screenshot: bool = False, profil: str | None = None,
                 dry_run: bool = False) -> None:
        self.state = state
        self.filtry = filtry
        self.proba_payment = proba_payment
        self.timing = timing
        # O1: screenshot domyślnie WYŁĄCZONY w gorącej ścieżce (koszt 8-15 s).
        self.screenshot = screenshot
        self.profil = profil
        self.dry_run = dry_run
        # O6: kolejka ofert do kupienia — oddziela polling od checkoutu.
        self._queue: "queue.Queue" = queue.Queue()
        self._stop = threading.Event()
        self._worker: threading.Thread | None = None

    def _kup(self, oferta) -> None:
        if self.state.status != SessionStatus.READY:
            return
        if oferta.seller_id is None:
            return
        if self.dry_run:
            print(f"[daemon] dry-run: wykryto ofertę {oferta.id} — pomijam rezerwację", flush=True)
            return
        konto = KonfiguracjaKonta(cookies=self.state.cookies, user_id=self.state.user_id)
        w = zrealizuj_zakup(oferta.id, oferta.seller_id, konto,
                            proba_payment=self.proba_payment, profil=self.profil)
        if self.timing or self.screenshot:
            # O1: async — raport timingów od razu, screenshot Camoufox w tle.
            evidence.zapisz_dowody_async(
                w, prefix=f"daemon_{oferta.id}", timings=self.timing,
                screenshot=self.screenshot, payment=self.proba_payment, profil=self.profil,
            )
        self.state.record_reservation()

    def _worker_loop(self) -> None:
        """Konsumuje kolejkę ofert i wykonuje checkout (niezależnie od pollingu)."""
        while not self._stop.is_set():
            try:
                oferta = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self._kup(oferta)
            except Exception as exc:
                self.state.record_error(f"purchase worker error: {exc}")
            finally:
                self._queue.task_done()

    def run(self, stop_event: threading.Event) -> None:
        from .detection import monitoruj

        self._stop = stop_event
        self._worker = threading.Thread(target=self._worker_loop, daemon=True,
                                        name="purchase-worker")
        self._worker.start()

        # O2: współdzielona sesja keep-alive dla detekcji. Osobny wariant "detekcja"
        # (NIE "glowna") bo wątek POLL i WORKER działają równolegle, a curl_cffi
        # Session nie jest thread-safe. Sesja detekcji ma własne keep-alive połączenie;
        # worker checkoutu używa wariantów "glowna"/"pickup" (prewarm w run_daemon).
        konto = KonfiguracjaKonta(cookies=self.state.cookies)
        sesja_detekcji = None
        if self.state.cookies:
            try:
                sesja_detekcji = pobierz_sesje(konto, "detekcja")
            except Exception:
                sesja_detekcji = None

        def _cb(nowe):
            for o in nowe:
                self._queue.put(o)

        while not stop_event.is_set():
            if self.state.status == SessionStatus.READY:
                try:
                    monitoruj(self.filtry, interwal=POLL_INTERVAL, callback=_cb,
                              max_iter=1, cookies=self.state.cookies,
                              session=sesja_detekcji, limit=POLL_LIMIT)
                except Exception as exc:
                    self.state.record_error(f"purchase loop error: {exc}")
                    self.state.set_status(SessionStatus.REFRESHING)
            stop_event.wait(1.0)


def _start_multi_konta(konta, filtry, proba_payment, refresh_interval_min,
                       timing, screenshot, dry_run, stop) -> None:
    """Startuje wątki RefreshLoop + PurchaseLoop dla każdego konta (nie blokuje)."""
    for k in konta:
        state = SessionState()
        from .config import wczytaj_cookies
        try:
            state.cookies = wczytaj_cookies(k["cookies_path"])
            if state.is_ready():
                state.set_status(SessionStatus.READY)
        except Exception:
            pass

        if state.status == SessionStatus.READY:
            try:
                prewarm_sesje(KonfiguracjaKonta(cookies=state.cookies))
            except Exception as exc:
                print(f"[daemon] prewarm sesji nie powiódł się: {exc}", flush=True)

        refresh = RefreshLoop(profile=k["profil"], interval_min=refresh_interval_min)
        purchase = PurchaseLoop(state=state, filtry=filtry, proba_payment=proba_payment,
                                timing=timing, screenshot=screenshot, profil=k["profil"],
                                dry_run=dry_run)

        t_refresh = threading.Thread(target=refresh.run, args=(state, stop), daemon=True,
                                     name=f"refresh-{k['profil']}")
        t_purchase = threading.Thread(target=purchase.run, args=(stop,), daemon=True,
                                      name=f"purchase-{k['profil']}")
        t_refresh.start()
        t_purchase.start()


def run_daemon_multi(konta, filtry, proba_payment, refresh_interval_min,
                     timing=True, screenshot=False, dry_run=False,
                     block=True) -> None:
    """Parallel multi-konto: dla każdego konta osobny RefreshLoop + PurchaseLoop.

    Gdy block=False, startuje wątki i zwraca natychmiast (do testów / kompozycji).
    """
    stop = threading.Event()
    _start_multi_konta(konta, filtry, proba_payment, refresh_interval_min,
                       timing, screenshot, dry_run, stop)

    if not block:
        return

    def _shutdown(signum, frame):
        print(f"[daemon] sygnał {signum}, zamykam...", flush=True)
        stop.set()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    while not stop.is_set():
        stop.wait(10.0)

    print("[daemon] zakończono (multi-konto).", flush=True)


def run_daemon(profile, filtry, proba_payment, refresh_interval_min, cookies_path,
               timing: bool = True, screenshot: bool = False, dry_run: bool = False) -> None:
    """Backward-compat: pojedyncze konto deleguje do run_daemon_multi."""
    run_daemon_multi(
        [{"cookies_path": cookies_path, "profil": profile}],
        filtry=filtry, proba_payment=proba_payment,
        refresh_interval_min=refresh_interval_min,
        timing=timing, screenshot=screenshot, dry_run=dry_run,
    )
