from vintedbot import incognia


def test_wygeneruj_token_wolaj_node(monkeypatch):
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)

        class R:
            returncode = 0
            stdout = "TOKEN\n"
            stderr = ""

        return R()

    monkeypatch.setattr(incognia.subprocess, "run", fake_run)
    tok = incognia.wygeneruj_token("sid-1")
    assert tok == "TOKEN"
    assert calls[0][0] == "node"
    assert calls[0][2] == "sid-1"


def test_wygeneruj_token_blad_node(monkeypatch):
    def fake_run(cmd, **kw):
        class R:
            returncode = 1
            stdout = ""
            stderr = "boom"

        return R()

    monkeypatch.setattr(incognia.subprocess, "run", fake_run)
    try:
        incognia.wygeneruj_token("sid-1")
        assert False, "powinno rzucić RuntimeError"
    except RuntimeError as e:
        assert "boom" in str(e)


def test_pobierz_lub_wygeneruj_token_cache_hit(monkeypatch):
    calls = [0]

    def fake_run(cmd, **kw):
        calls[0] += 1

        class R:
            returncode = 0
            stdout = f"TOKEN_{calls[0]}\n"
            stderr = ""

        return R()

    monkeypatch.setattr(incognia.subprocess, "run", fake_run)
    incognia.czysc_cache_tokenu()

    tok1 = incognia.pobierz_lub_wygeneruj_token("sid-cache", max_age_s=60.0)
    assert tok1 == "TOKEN_1"
    assert calls[0] == 1

    # Drugie wywołanie w oknie TTL nie powinno wywoływać Node.js
    tok2 = incognia.pobierz_lub_wygeneruj_token("sid-cache", max_age_s=60.0)
    assert tok2 == "TOKEN_1"
    assert calls[0] == 1


def test_prewarm_worker(monkeypatch):
    calls = [0]

    def fake_run(cmd, **kw):
        calls[0] += 1

        class R:
            returncode = 0
            stdout = f"TOKEN_PREWARM\n"
            stderr = ""

        return R()

    monkeypatch.setattr(incognia.subprocess, "run", fake_run)
    incognia.czysc_cache_tokenu()

    stop_event = incognia.start_prewarm_worker("sid-worker", interval_s=0.05)
    import time
    time.sleep(0.12)
    stop_event.set()

    assert calls[0] >= 2
    tok = incognia.pobierz_lub_wygeneruj_token("sid-worker")
    assert tok == "TOKEN_PREWARM"