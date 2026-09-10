from urllib.parse import urlencode

from vintedbot.detection import pobierz_oferty, monitoruj, _nastepny_interwal, _sesja_aktywna, utrzymuj_sesje
from vintedbot.models import Filtry, Oferta


def test_pobierz_oferty_buduje_url_z_filtrami(fake_http):
    payload = '{"items":[{"id":1,"title":"A","price":{"amount":"5.0","currency_code":"PLN"}}]}'
    base = "https://www.vinted.pl/api/v2/catalog/items"
    params = {"brand_ids": "53", "search_text": "nike", "per_page": 20, "order": "newest_first"}
    url = f"{base}?{urlencode(params)}"
    fake_http(url, payload)

    filtry = Filtry(brand_ids=[53], search_text="nike")
    oferty = pobierz_oferty(filtry)

    assert len(oferty) == 1
    assert oferty[0].id == 1


def test_monitoruj_wykrywa_tylko_nowe_id(monkeypatch):
    """monitoruj wywołuje callback tylko dla ID, których wcześniej nie widział."""
    sekwencja = [
        [{"id": 1, "title": "A", "price": {"amount": "5.0", "currency_code": "PLN"}}],
        [
            {"id": 2, "title": "B", "price": {"amount": "5.0", "currency_code": "PLN"}},
            {"id": 1, "title": "A", "price": {"amount": "5.0", "currency_code": "PLN"}},
        ],
    ]
    i = 0

    def _pobierz(filtry, limit=96, cookies=None, session=None):
        nonlocal i
        lista = sekwencja[i]
        i += 1
        from vintedbot.models import Oferta
        return [Oferta.model_validate(x) for x in lista]

    monkeypatch.setattr("vintedbot.detection.pobierz_oferty", _pobierz)
    monkeypatch.setattr("time.sleep", lambda s: None)

    zebrane = []

    def _cb(nowe):
        zebrane.extend(nowe)

    monitoruj(Filtry(), interwal=0.0, callback=_cb, max_iter=2)

    assert [o.id for o in zebrane] == [1, 2]  # 1 tylko raz, potem 2


def test_backoff_wzrasta_do_maksimum():
    assert _nastepny_interwal(1, jitter=0.0) == 2.0
    assert _nastepny_interwal(2, jitter=0.0) == 4.0
    assert _nastepny_interwal(5, jitter=0.0) == 8.0


def test_backoff_jitter_nie_przekracza_capu():
    assert _nastepny_interwal(5, jitter=0.2) <= 8.0


def test_sesja_aktywna_po_login():
    dane = {"user": {"login": "maksks0", "id": 3180346878}}
    assert _sesja_aktywna(dane) is True


def test_sesja_nieaktywna_bez_login():
    dane = {"user": {}}
    assert _sesja_aktywna(dane) is False


def test_sesja_nieaktywna_none():
    assert _sesja_aktywna(None) is False


def test_utrzymuj_sesje_wykonuje_n_cykli(monkeypatch):
    """utrzymuj_sesje woła odswiez_token tyle razy, ile max_cykli."""
    wywolania = []

    def _odswiez(cookies):
        wywolania.append(cookies)
        return cookies

    monkeypatch.setattr("vintedbot.detection.odswiez_token", _odswiez)
    monkeypatch.setattr("vintedbot.detection.time.sleep", lambda s: None)

    utrzymuj_sesje({"access_token_web": "x"}, co_ile_s=0.0, max_cykli=3)

    assert len(wywolania) == 3


def test_monitoruj_wewn_spojne_z_rtt(monkeypatch):
    """latencja wewnętrzna mierzona dla każdej udanej iteracji (niezależnie od callbacku)."""
    from vintedbot.measurement import LatencyRecorder

    payload = [{"id": 1, "title": "A", "price": {"amount": "5.0", "currency_code": "PLN"}}]

    def _pobierz(filtry, limit=96, cookies=None, session=None):
        from vintedbot.models import Oferta
        return [Oferta.model_validate(x) for x in payload]

    monkeypatch.setattr("vintedbot.detection.pobierz_oferty", _pobierz)
    monkeypatch.setattr("vintedbot.detection.time.sleep", lambda s: None)

    rtt = LatencyRecorder()
    wewn = LatencyRecorder()
    monitoruj(Filtry(), interwal=0.0, callback=lambda n: None, max_iter=3,
              recorder=rtt, recorder_wewn=wewn)

    assert rtt.count == 3
    assert wewn.count == 3
    assert wewn.p50 >= 0


def test_utworz_transakcje_buduje_body(monkeypatch):
    import json
    from vintedbot.detection import utworz_transakcje
    from vintedbot.models import KonfiguracjaKonta

    captured = {}

    class _Resp:
        status_code = 200
        content = json.dumps({"conversation": {"transaction": {"id": "T123"}}}).encode()

        def raise_for_status(self):
            pass

    def fake_post(url, **kw):
        captured["url"] = url
        captured["json"] = kw["json"]
        return _Resp()

    monkeypatch.setattr("vintedbot.detection.creq.post", fake_post)
    txn = utworz_transakcje(item_id=7, seller_id=9, konto=KonfiguracjaKonta())
    assert txn == "T123"
    # [UDOWODNIONE] przeglądarka używa /api/v2/conversations (nie /inquiries).
    assert captured["url"] == "https://www.vinted.pl/api/v2/conversations"
    assert captured["json"] == {"initiator": "buy", "item_id": 7, "opposite_user_id": 9}


def test_sprawdz_dostepnosc(monkeypatch):
    import json
    from vintedbot.detection import sprawdz_dostepnosc
    from vintedbot.models import KonfiguracjaKonta

    captured = {}

    class _Resp:
        status_code = 200
        content = json.dumps({"purchase": {"user": {"buy": {"available": True}}}}).encode()

        def raise_for_status(self):
            pass

    def fake_post(url, **kw):
        captured["url"] = url
        captured["json"] = kw["json"]
        return _Resp()

    monkeypatch.setattr("vintedbot.detection.creq.post", fake_post)
    res = sprawdz_dostepnosc(buyer_id=123, item_ids=[456, 789], konto=KonfiguracjaKonta())
    assert res["purchase"]["user"]["buy"]["available"] is True
    assert captured["url"] == "https://api.vinted.pl/checkout/purchases/check_availability"
    assert captured["json"] == {"buyer_id": "123", "item_ids": ["456", "789"]}


def test_ekstrahuj_pierwszy_item_z_chunka():
    from vintedbot.detection import ekstrahuj_pierwszy_item_z_chunka
    
    # Niepełny chunk ze strumienia sieciowego
    chunk = b'{"items":[{"id":9988,"title":"Bluza Nike","price":{"amount":"120.0","currency_code":"PLN"},"user":{"id":5544}},{"id":1122'
    item = ekstrahuj_pierwszy_item_z_chunka(chunk)
    assert item is not None
    assert item["id"] == 9988
    assert item["title"] == "Bluza Nike"
    assert item["user"]["id"] == 5544


def test_pobierz_oferty_early_trigger(monkeypatch):
    from vintedbot.detection import pobierz_oferty
    from vintedbot.models import Filtry
    
    full_payload = b'{"items":[{"id":7788,"title":"Buty","price":{"amount":"200.0","currency_code":"PLN"},"user":{"id":1122}}]}'
    
    class _MockStreamResp:
        status_code = 200
        headers = {"cf-ray": "test-ray-WAW"}
        
        def iter_content(self, chunk_size=4096):
            yield full_payload
            
        def raise_for_status(self):
            pass

    monkeypatch.setattr("vintedbot.detection.creq.get", lambda *a, **kw: _MockStreamResp())
    
    early_items = []
    def _on_early(o):
        early_items.append(o)
        
    oferty = pobierz_oferty(Filtry(), on_early_item=_on_early)
    assert len(oferty) == 1
    assert len(early_items) == 1
    assert early_items[0].id == 7788
    assert early_items[0].seller_id == 1122
    assert early_items[0].detection_span["type"] == "NET_STREAM_TTFB"