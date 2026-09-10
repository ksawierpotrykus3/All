"""Testy jednostkowe modułu json_utils."""
from vintedbot.json_utils import json_loads, json_dumps, json_dumps_bytes


def test_json_loads_str_and_bytes():
    payload = '{"id": 123, "title": "Test"}'
    res1 = json_loads(payload)
    assert res1 == {"id": 123, "title": "Test"}

    res2 = json_loads(payload.encode("utf-8"))
    assert res2 == {"id": 123, "title": "Test"}


def test_json_dumps():
    obj = {"status": "ok", "count": 5}
    dumped_str = json_dumps(obj)
    assert "status" in dumped_str
    assert "ok" in dumped_str

    dumped_bytes = json_dumps_bytes(obj)
    assert isinstance(dumped_bytes, bytes)
    assert b"status" in dumped_bytes
