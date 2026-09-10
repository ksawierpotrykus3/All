# bot/tests/test_daemon.py
from vintedbot.daemon import PurchaseLoop
from vintedbot.session_state import SessionState, SessionStatus
from vintedbot.models import Filtry, Oferta
import threading


def _oferta(id, seller):
    return Oferta.model_validate({"id": id, "title": "A",
                                  "price": {"amount": "5", "currency_code": "PLN"},
                                  "user": {"id": seller}})


def test_purchase_loop_nie_rezerwuje_gdy_nie_ready(monkeypatch):
    state = SessionState()
    state.status = SessionStatus.REFRESHING

    calls = []

    def fake_zrealizuj(*a, **kw):
        calls.append(a)
        return None

    monkeypatch.setattr("vintedbot.daemon.zrealizuj_zakup", fake_zrealizuj)

    loop = PurchaseLoop(state=state, filtry=Filtry(), proba_payment=False)
    loop._kup(_oferta(1, 10))

    assert calls == []


def test_purchase_loop_rezerwuje_gdy_ready(monkeypatch):
    state = SessionState()
    state.status = SessionStatus.READY
    state.cookies = {"a": "1"}

    calls = []

    def fake_zrealizuj(*a, **kw):
        calls.append(a)
        return None

    monkeypatch.setattr("vintedbot.daemon.zrealizuj_zakup", fake_zrealizuj)
    monkeypatch.setattr("vintedbot.daemon.KonfiguracjaKonta",
                        lambda cookies, user_id=None: type("K", (), {"cookies": cookies, "user_id": user_id})())

    loop = PurchaseLoop(state=state, filtry=Filtry(), proba_payment=False)
    loop._kup(_oferta(1, 10))

    assert len(calls) == 1
    assert calls[0][0] == 1  # item_id
    assert calls[0][1] == 10  # seller_id
    assert state.reservations == 1


def test_purchase_loop_pomija_brak_seller(monkeypatch):
    state = SessionState()
    state.status = SessionStatus.READY
    state.cookies = {"a": "1"}

    calls = []

    def fake_zrealizuj(*a, **kw):
        calls.append(a)
        return None

    monkeypatch.setattr("vintedbot.daemon.zrealizuj_zakup", fake_zrealizuj)
    monkeypatch.setattr("vintedbot.daemon.KonfiguracjaKonta",
                        lambda cookies: type("K", (), {"cookies": cookies})())

    loop = PurchaseLoop(state=state, filtry=Filtry(), proba_payment=False)
    o = Oferta.model_validate({"id": 2, "title": "B",
                               "price": {"amount": "5", "currency_code": "PLN"}})
    loop._kup(o)

    assert calls == []


def test_run_daemon_startuje_n_kont(monkeypatch):
    from vintedbot import daemon as d

    started_refresh = []
    started_purchase = []

    class FakeRefreshLoop:
        def __init__(self, profile, interval_min):
            self.profile = profile
            self.interval_min = interval_min
        def run(self, state, stop):
            started_refresh.append(self.profile)

    class FakePurchaseLoop:
        def __init__(self, state, filtry, proba_payment, timing, screenshot, profil, dry_run):
            self.profil = profil
        def run(self, stop):
            started_purchase.append(self.profil)

    monkeypatch.setattr(d, "RefreshLoop", FakeRefreshLoop)
    monkeypatch.setattr(d, "PurchaseLoop", FakePurchaseLoop)
    monkeypatch.setattr(d, "SessionState", lambda: type("S", (), {"cookies": {}, "status": None, "is_ready": lambda: False, "set_status": lambda s: None})())
    monkeypatch.setattr("vintedbot.config.wczytaj_cookies", lambda p: {})

    konta = [
        {"cookies_path": "/tmp/c1.txt", "profil": "/tmp/p1"},
        {"cookies_path": "/tmp/c2.txt", "profil": "/tmp/p2"},
    ]

    d.run_daemon_multi(konta, filtry=d.Filtry(), proba_payment=False,
                       refresh_interval_min=4, timing=False, screenshot=False,
                       dry_run=True, block=False)

    assert len(started_refresh) == 2
    assert len(started_purchase) == 2
    assert {p for p in started_refresh} == {"/tmp/p1", "/tmp/p2"}
    assert {p for p in started_purchase} == {"/tmp/p1", "/tmp/p2"}