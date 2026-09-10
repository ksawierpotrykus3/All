# bot/tests/test_session_state.py
import json

from vintedbot.session_state import SessionState, SessionStatus


def test_start_unknown():
    s = SessionState()
    assert s.status == SessionStatus.UNKNOWN
    assert s.cookies == {}
    assert s.reservations == 0


def test_set_status_i_snapshot():
    s = SessionState()
    s.set_status(SessionStatus.READY)
    snap = s.snapshot()
    assert snap["status"] == "ready"
    assert snap["reservations"] == 0


def test_record_reservation():
    s = SessionState()
    s.record_reservation()
    s.record_reservation()
    assert s.reservations == 2


def test_record_error():
    s = SessionState()
    s.record_error("boom")
    assert s.errors == ["boom"]


def test_is_ready_true(monkeypatch):
    import vintedbot.session_state as ss

    class R:
        status_code = 200
        content = json.dumps({"user": {"login": "maksks0", "id": 1}}).encode()

    monkeypatch.setattr(ss.creq, "get", lambda url, **kw: R())
    s = SessionState()
    s.cookies = {"a": "1"}
    assert s.is_ready() is True


def test_is_ready_false_401(monkeypatch):
    import vintedbot.session_state as ss

    class R:
        status_code = 401
        content = b"{}"

    monkeypatch.setattr(ss.creq, "get", lambda url, **kw: R())
    s = SessionState()
    s.cookies = {"a": "1"}
    assert s.is_ready() is False


def test_is_ready_false_anon(monkeypatch):
    import vintedbot.session_state as ss

    class R:
        status_code = 200
        content = json.dumps({"user": {}}).encode()

    monkeypatch.setattr(ss.creq, "get", lambda url, **kw: R())
    s = SessionState()
    s.cookies = {"a": "1"}
    assert s.is_ready() is False