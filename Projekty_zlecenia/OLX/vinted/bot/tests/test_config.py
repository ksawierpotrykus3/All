from vintedbot import config


def test_stale_domyslne():
    assert config.IMPERSONATE == "firefox135"
    assert config.PAY_IN_METHOD == "1"


def test_wczytaj_cookies_json(tmp_path):
    import json
    p = tmp_path / "c.json"
    p.write_text(json.dumps([
        {"name": "a", "value": "1"},
        {"name": "b", "value": "2"},
    ]), encoding="utf-8")
    c = config.wczytaj_cookies(p)
    assert c == {"a": "1", "b": "2"}


def test_wczytaj_cookies_netscape(tmp_path):
    p = tmp_path / "c.txt"
    p.write_text(
        "# Netscape HTTP Cookie File\n\n"
        ".vinted.pl\tTRUE\t/\tTRUE\t0\taccess_token_web\txyz\n",
        encoding="utf-8",
    )
    c = config.wczytaj_cookies(p)
    assert c["access_token_web"] == "xyz"


def test_wczytaj_cookies_json_pomija_bez_name(tmp_path):
    import json
    p = tmp_path / "c.json"
    p.write_text(json.dumps([{"value": "no-name"}, {"name": "a", "value": "1"}]), encoding="utf-8")
    assert config.wczytaj_cookies(p) == {"a": "1"}