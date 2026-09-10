"""Testy jednostkowe modułu evidence.py."""
import json
import tempfile
from pathlib import Path
from PIL import Image

from vintedbot.evidence import (
    zapisz_raport_timingow,
    _wypal_timestamp,
    zapisz_dowody,
    zapisz_dowody_async,
)
from vintedbot.models import WynikCheckoutu


def test_zapisz_raport_timingow():
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        wynik = {"checkout_id": "123", "timings": {"transaction": 100, "payment": 200}}
        p = zapisz_raport_timingow(wynik, prefix="test_item", output_dir=out_dir)
        assert p is not None
        assert p.exists()
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["prefix"] == "test_item"
        assert data["result"]["checkout_id"] == "123"
        assert "ts_wall" in data


def test_wypal_timestamp():
    with tempfile.TemporaryDirectory() as tmp:
        img_path = Path(tmp) / "test_shot.png"
        img = Image.new("RGB", (800, 600), color=(50, 50, 50))
        img.save(img_path)

        step_marks = {
            "transaction": {"start_iso": "12:00:00.100Z", "end_iso": "12:00:01.200Z", "dur_ms": 1100},
            "payment": {"start_iso": "12:00:01.200Z", "end_iso": "12:00:02.500Z", "dur_ms": 1300},
        }
        timings = {"transaction": 1100, "payment": 1300}
        payment_info = {
            "status_payment": 200,
            "payment_status": "SUCCESS",
            "action_type": "REDIRECT",
            "error_code": None,
        }

        _wypal_timestamp(
            img_path,
            kind="bramka_platnosci",
            url="https://psp.adyen.com/pay",
            step_marks=step_marks,
            timings=timings,
            payment_info=payment_info,
        )

        assert img_path.exists()
        with Image.open(img_path) as loaded:
            assert loaded.size == (800, 600)


def test_zapisz_dowody_model_pydantic():
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        w = WynikCheckoutu(
            checkout_id="chk_777",
            status_build=200,
            status_payment=200,
            payment_status="SUCCESS",
            redirect_url="https://pay.example.com",
            timings={"transaction": 500, "payment": 300},
        )
        paths = zapisz_dowody(w, prefix="test_pydantic", timings=True, screenshot=False, output_dir=out_dir)
        assert "timing_report" in paths
        rep_path = Path(paths["timing_report"])
        assert rep_path.exists()
