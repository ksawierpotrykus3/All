from urllib.parse import urlencode

from click.testing import CliRunner

import vintedbot.detection as detection

from vintedbot.cli import cli


def test_cli_monitor_drukuje_oferty(fake_http):
    payload = '{"items":[{"id":7,"title":"X","price":{"amount":"3.0","currency_code":"PLN"}}]}'
    base = "https://www.vinted.pl/api/v2/catalog/items"
    params = {"brand_ids": "53", "per_page": 10, "order": "newest_first"}
    url = f"{base}?{urlencode(params)}"
    fake_http(url, payload)

    runner = CliRunner()
    result = runner.invoke(cli, ["monitor", "--brand", "53", "--limit", "10"])

    assert result.exit_code == 0
    assert "7" in result.output


def test_keepalive_wywoluje_utrzymuj_sesje(monkeypatch, tmp_path):
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")

    wywolania = []

    def _utrzymuj(ck, co_ile_s=1800.0):
        wywolania.append((ck, co_ile_s))

    monkeypatch.setattr(detection, "utrzymuj_sesje", _utrzymuj)

    runner = CliRunner()
    result = runner.invoke(cli, ["keepalive", "--cookies", str(cookies), "--co-ile", "10"])

    assert result.exit_code == 0
    assert len(wywolania) == 1
    assert wywolania[0][1] == 10.0


def test_bench_drukuje_raport_json(fake_http):
    payload = '{"items":[{"id":42,"title":"T","price":{"amount":"9.0","currency_code":"PLN"}}]}'
    base = "https://www.vinted.pl/api/v2/catalog/items"
    params = {"brand_ids": "53", "per_page": 10, "order": "newest_first"}
    url = f"{base}?{urlencode(params)}"
    fake_http(url, payload)

    runner = CliRunner()
    result = runner.invoke(cli, ["bench", "--brand", "53", "--max-iter", "2"])

    assert result.exit_code == 0
    assert '"rtt"' in result.output
    assert '"wewn"' in result.output
    assert '"count"' in result.output
    assert '"p50"' in result.output


def test_bench_zapisuje_raport(fake_http, tmp_path):
    payload = '{"items":[{"id":42,"title":"T","price":{"amount":"9.0","currency_code":"PLN"}}]}'
    base = "https://www.vinted.pl/api/v2/catalog/items"
    params = {"brand_ids": "53", "per_page": 10, "order": "newest_first"}
    url = f"{base}?{urlencode(params)}"
    fake_http(url, payload)

    out = tmp_path / "bench.json"
    runner = CliRunner()
    result = runner.invoke(cli, ["bench", "--brand", "53", "--max-iter", "2", "--out", str(out)])

    assert result.exit_code == 0
    assert '"count"' in out.read_text(encoding="utf-8")
    # Po naprawie: wewn.count musi być równe rtt.count (pierswsza iteracja też mierzy wewn).
    import json as _json
    rep = _json.loads(out.read_text(encoding="utf-8"))
    assert rep["wewn"]["count"] == rep["rtt"]["count"]


def test_autocop_konczy_po_detekcji(fake_http):
    payload = '{"items":[{"id":42,"title":"T","price":{"amount":"9.0","currency_code":"PLN"}}]}'
    base = "https://www.vinted.pl/api/v2/catalog/items"
    params = {"brand_ids": "53", "per_page": 10, "order": "newest_first"}
    url = f"{base}?{urlencode(params)}"
    fake_http(url, payload)

    runner = CliRunner()
    result = runner.invoke(cli, ["autocop", "--brand", "53", "--max-iter", "1", "--no-checkout"])

    assert result.exit_code == 0
    assert "42" in result.output


def test_cli_daemon_rejestruje_sie():
    runner = CliRunner()
    result = runner.invoke(cli, ["daemon", "--help"])
    assert result.exit_code == 0
    assert "--payment" in result.output
    assert "--interval" in result.output


def test_cli_monitor_z_pełnymi_filtrami(fake_http):
    payload = '{"items":[{"id":7,"title":"X","price":{"amount":"3.0","currency_code":"PLN"}}]}'
    base = "https://www.vinted.pl/api/v2/catalog/items"
    params = {
        "brand_ids": "53",
        "size_ids": "208",
        "status_ids": "6",
        "price_from": 10.0,
        "price_to": 50.0,
        "per_page": 10,
        "order": "newest_first",
    }
    url = f"{base}?{urlencode(params)}"
    fake_http(url, payload)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "monitor",
            "--brand", "53",
            "--size", "208",
            "--status", "6",
            "--price-from", "10",
            "--price-to", "50",
            "--limit", "10",
        ],
    )

    assert result.exit_code == 0
    assert "7" in result.output


def test_cli_daemon_multi_konta_help():
    from click.testing import CliRunner
    from vintedbot.cli import cli
    runner = CliRunner()
    result = runner.invoke(cli, ["daemon", "--help"])
    assert result.exit_code == 0
    assert "multiple" in result.output or "--cookies" in result.output