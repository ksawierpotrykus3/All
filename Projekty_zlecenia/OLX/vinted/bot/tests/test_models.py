from vintedbot.models import Filtry, Oferta, KonfiguracjaKonta, WynikCheckoutu


def test_filtry_domyslne_puste():
    f = Filtry()
    assert f.brand_ids == []
    assert f.price_from is None


def test_oferta_parsuje_odpowiedz_api():
    raw = {
        "id": 123,
        "title": "Kurtka",
        "price": {"amount": "10.0", "currency_code": "PLN"},
        "brand_title": "Nike",
    }
    o = Oferta.model_validate(raw)
    assert o.id == 123
    assert o.title == "Kurtka"
    assert o.cena == 10.0


def test_oferta_parsuje_seller_id():
    raw = {"id": 1, "title": "A", "price": {"amount": "5.0", "currency_code": "PLN"},
           "user": {"id": 99}}
    o = Oferta.model_validate(raw)
    assert o.seller_id == 99


def test_oferta_bez_user():
    raw = {"id": 1, "title": "A", "price": {"amount": "5.0", "currency_code": "PLN"}}
    o = Oferta.model_validate(raw)
    assert o.seller_id is None


def test_konfiguracja_konta():
    k = KonfiguracjaKonta(cookies={"a": "1"})
    assert k.csrf == "75f6c9fa-dc8e-4e52-a000-e09dd4084b3e"
    assert k.cookies == {"a": "1"}


def test_wynik_checkoutu_timings():
    w = WynikCheckoutu(purchase_id="p1")
    w.timings["build"] = 100.0
    assert w.timings["build"] == 100.0