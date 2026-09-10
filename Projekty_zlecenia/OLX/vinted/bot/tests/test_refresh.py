# bot/tests/test_refresh.py
from vintedbot.refresh import RefreshLoop, _eksportuj_cookies
from vintedbot.session_state import SessionState, SessionStatus


def test_eksportuj_cookies_z_listy():
    raw = [
        {"name": "a", "value": "1", "domain": ".vinted.pl", "path": "/",
         "expires": -1, "httpOnly": False, "secure": False, "sameSite": "Lax"},
        {"name": "b", "value": "2", "domain": ".vinted.pl", "path": "/",
         "expires": -1, "httpOnly": True, "secure": True, "sameSite": "Lax"},
    ]
    assert _eksportuj_cookies(raw) == {"a": "1", "b": "2"}


def test_run_once_ready(monkeypatch):
    class FakePage:
        def goto(self, url, **kw):
            return None

    class FakeCtx:
        def new_page(self):
            return FakePage()
        def cookies(self):
            return [{"name": "access_token_web", "value": "TOK", "domain": ".vinted.pl",
                     "path": "/", "expires": -1, "httpOnly": True, "secure": True, "sameSite": "Lax"}]

    class FakeCamoufox:
        def __init__(self, **kw):
            pass
        def __enter__(self):
            return FakeCtx()
        def __exit__(self, *a):
            return False

    monkeypatch.setattr("vintedbot.refresh.Camoufox", FakeCamoufox)
    monkeypatch.setattr("vintedbot.refresh._czy_zalogowany", lambda page: ("maksks0", 1))

    state = SessionState()
    loop = RefreshLoop(profile="profil", interval_min=4)
    ok = loop.run_once(state)

    assert ok is True
    assert state.status == SessionStatus.READY
    assert state.cookies["access_token_web"] == "TOK"
    assert state.login == "maksks0"


def test_run_once_needs_login(monkeypatch):
    class FakePage:
        def goto(self, url, **kw):
            return None

    class FakeCtx:
        def new_page(self):
            return FakePage()
        def cookies(self):
            return []

    class FakeCamoufox:
        def __init__(self, **kw):
            pass
        def __enter__(self):
            return FakeCtx()
        def __exit__(self, *a):
            return False

    monkeypatch.setattr("vintedbot.refresh.Camoufox", FakeCamoufox)
    monkeypatch.setattr("vintedbot.refresh._czy_zalogowany", lambda page: (None, None))
    monkeypatch.setattr("vintedbot.refresh.TIMEOUT_S", 0.05)
    monkeypatch.setattr("vintedbot.refresh.MANUAL_LOGIN_TIMEOUT_S", 0.05)
    monkeypatch.setattr("vintedbot.refresh.POLL_S", 0.01)

    state = SessionState()
    loop = RefreshLoop(profile="profil", interval_min=4)
    ok = loop.run_once(state)

    assert ok is False
    assert state.status == SessionStatus.NEEDS_LOGIN