"""Tests for MVP OCR engines."""

import numpy as np

from mvp.bot.ocr import (
    _ALLIANCE_RE,
    _CHAT_RE,
    _DETAILS_RE,
    _EXPLORE_RE,
    ChatOCR,
    TimerOCR,
)


def test_parse_coords_handles_colon() -> None:
    assert ChatOCR._parse_coords("1234:5678") == (1234, 5678)


def test_parse_coords_handles_comma() -> None:
    assert ChatOCR._parse_coords("State 12, 345") == (12, 345)


def test_parse_coords_returns_none_for_garbage() -> None:
    assert ChatOCR._parse_coords("no coords here") is None


def test_timer_ocr_parse_time_handles_mmss() -> None:
    assert TimerOCR._parse_time("01:30") == 90
    assert TimerOCR._parse_time("00:07:27") == 447
    assert TimerOCR._parse_time("00:00:04") == 4


def test_timer_ocr_parse_time_rejects_invalid() -> None:
    assert TimerOCR._parse_time("42") is None
    assert TimerOCR._parse_time("xx") is None
    assert TimerOCR._parse_time("00:99:00") is None


def test_timer_ocr_parse_time_with_surrounding_text() -> None:
    assert TimerOCR._parse_time("Timer: 00:05:12 left") == 312
    assert TimerOCR._parse_time("Time 02:45") == 165


def test_timer_ocr_white_mask_pass_reads_helka3_fixture() -> None:
    """Fixture from helka3.png: timer 00:11:18 (678s) overlapping player names.

    Player names like [MAVE]Zebra use bright orange pixels while the timer
    uses white pixels — the HSV white-mask pass must isolate and read the
    timer correctly despite the overlap.
    """
    import pathlib

    import cv2  # type: ignore[import]

    fixture = (
        pathlib.Path(__file__).parent.parent.parent
        / "tests"
        / "fixtures"
        / "timer_crops"
        / "helka3_00_11_18.png"
    )
    if not fixture.exists():
        import pytest

        pytest.skip(f"Fixture not found: {fixture}")

    image = cv2.imread(str(fixture))
    assert image is not None, f"Could not read fixture: {fixture}"

    timer = TimerOCR()
    timer.initialize()
    result = timer.read_timer(image)
    assert result == 678, f"Expected 678s (00:11:18), got {result!r}"


def test_timer_ocr_reads_helka1_and_helka2_fixtures() -> None:
    """Fixtures from helka.png (00:28:51 -> 1731s) and helka2.png (00:28:44 -> 1724s)."""
    import pathlib

    import cv2  # type: ignore[import]

    fixtures_dir = (
        pathlib.Path(__file__).parent.parent.parent / "tests" / "fixtures" / "timer_crops"
    )
    timer = TimerOCR()
    timer.initialize()

    cases = [
        ("helka_crop.png", 1731),
        ("helka2_crop.png", 1724),
    ]
    for fname, expected in cases:
        fixture_path = fixtures_dir / fname
        if not fixture_path.exists():
            continue
        image = cv2.imread(str(fixture_path))
        assert image is not None
        result = timer.read_timer(image)
        assert result == expected, f"{fname}: expected {expected}, got {result}"


def test_timer_ocr_reads_helka_scrolled_with_macro_roi() -> None:
    """helka_scrolled.png cropped with macro _ROI_TIMER (zoomed view) must read 5s (00:00:05)."""
    import pathlib

    import cv2  # type: ignore[import]

    from mvp.bot.coordinates import GameROI, WindowContext
    from mvp.macro_def import _ROI_TIMER

    fixtures_dir = (
        pathlib.Path(__file__).parent.parent.parent / "tests" / "fixtures" / "timer_crops"
    )
    scrolled_path = fixtures_dir / "helka_scrolled.png"
    if not scrolled_path.exists():
        scrolled_path = pathlib.Path("helka_scrolled.png")
    if not scrolled_path.exists():
        import pytest

        pytest.skip("helka_scrolled.png not found")

    full_img = cv2.imread(str(scrolled_path))
    assert full_img is not None

    win = WindowContext(left=0, top=0, width=full_img.shape[1], height=full_img.shape[0])
    left, top, right, bottom = win.roi_to_frame_pixels(
        GameROI(**_ROI_TIMER), full_img.shape[1], full_img.shape[0]
    )
    cropped = full_img[top:bottom, left:right]

    timer = TimerOCR()
    timer.initialize()
    result = timer.read_timer(cropped)
    assert result == 5, f"Expected 5s (00:00:05), got {result}"


# ── ChatOCR.find_helicopter_alert unit tests (mock EasyOCR) ─────────────────


def _make_block(text: str, x: int, y: int, w: int = 80, h: int = 14, conf: float = 0.95):
    """Create a fake EasyOCR result block: (bbox, text, conf)."""
    bbox = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
    return (bbox, text, conf)


def _make_ocr_with_results(blocks):
    """Monkey-patchable stub that replaces ChatOCR._reader.readtext."""

    class _Reader:
        def readtext(self, image, allowlist=None, detail=1):
            return blocks

    return _Reader()


def test_find_helicopter_alert_accepts_valid_message() -> None:
    """Standard 'Explore Treasure' card with 'State 742 X:528 Y:482' → detected."""
    ocr = ChatOCR()
    ocr._reader = _make_ocr_with_results(
        [
            _make_block("Explore Treasure", x=10, y=2),
            _make_block("I found a new treasure spot!", x=10, y=20),
            _make_block("State 742  X:528  Y:482", x=10, y=38),
        ]
    )
    image = __import__("numpy").zeros((60, 200, 3), dtype=__import__("numpy").uint8)
    result = ocr.find_helicopter_alert(image)
    assert result is not None
    assert result["coords_x"] == 528
    assert result["coords_y"] == 482


def test_find_helicopter_alert_rejects_state_xy_without_explore_header() -> None:
    """Alliance Help / Rally messages that contain 'State X Y' but NOT 'Explore' are rejected."""
    ocr = ChatOCR()
    ocr._reader = _make_ocr_with_results(
        [
            _make_block("Alliance Help Request", x=10, y=2),
            _make_block("State 742 X:528 Y:482", x=10, y=20),
        ]
    )
    image = __import__("numpy").zeros((40, 200, 3), dtype=__import__("numpy").uint8)
    result = ocr.find_helicopter_alert(image)
    assert result is None, "Should reject State X Y without Explore header"


def test_find_helicopter_alert_handles_ocr_misread_colon() -> None:
    """OCR misread: 'State 751X347 Yl381' (colon → l) must still be detected."""
    ocr = ChatOCR()
    ocr._reader = _make_ocr_with_results(
        [
            _make_block("Explore Treasure", x=10, y=2),
            _make_block("State 751X347 Yl381", x=10, y=38),
        ]
    )
    image = __import__("numpy").zeros((60, 200, 3), dtype=__import__("numpy").uint8)
    result = ocr.find_helicopter_alert(image)
    assert result is not None
    assert result["coords_x"] == 347
    assert result["coords_y"] == 381


def test_find_helicopter_alert_rejects_low_confidence() -> None:
    """Blocks below min_confidence threshold must be rejected before any pattern check."""
    ocr = ChatOCR(min_confidence=0.5)
    ocr._reader = _make_ocr_with_results(
        [
            _make_block("Explore Treasure", x=10, y=2, conf=0.2),
            _make_block("State 742 X:528 Y:482", x=10, y=38, conf=0.1),
        ]
    )
    image = __import__("numpy").zeros((60, 200, 3), dtype=__import__("numpy").uint8)
    result = ocr.find_helicopter_alert(image)
    assert result is None, "Low-confidence blocks must be filtered out"


def test_find_helicopter_alert_on_real_game_screenshot() -> None:
    """Integration test using the actual in-game 'Explore Treasure' alert screenshot.

    The image contains:
      - Header: 'Explore Treasure'
      - Body: 'I found a new treasure spot! Send troops to explore it together!'
      - State row: 'State 742  X:528  Y:482'
    EasyOCR misreads 'Y:' as 'Vi' — the [YV] regex must handle this.
    """
    import pathlib

    import cv2  # type: ignore[import]

    fixture = (
        pathlib.Path(__file__).parent.parent.parent
        / "tests"
        / "fixtures"
        / "timer_crops"
        / "helicopter_alert_state742_x528_y482.png"
    )
    if not fixture.exists():
        import pytest

        pytest.skip(f"Fixture not found: {fixture}")

    image = cv2.imread(str(fixture))
    assert image is not None

    ocr = ChatOCR()
    ocr.initialize()
    result = ocr.find_helicopter_alert(image)

    assert result is not None, "Should detect helicopter alert in real screenshot"
    assert result["coords_x"] == 528, f"Expected X=528, got {result.get('coords_x')}"
    assert result["coords_y"] == 482, f"Expected Y=482, got {result.get('coords_y')}"


def test_find_helicopter_alert_rejects_gather_card_in_fast_ocr() -> None:
    """Gather cards containing State/X/Y coordinates but lacking Explore header must be ignored."""
    import pathlib

    import cv2  # type: ignore[import]

    fixture = (
        pathlib.Path(__file__).parent.parent.parent
        / "tests"
        / "fixtures"
        / "timer_crops"
        / "gather_alert_state751_x369_y481.png"
    )
    if not fixture.exists():
        import pytest

        pytest.skip(f"Fixture not found: {fixture}")

    image = cv2.imread(str(fixture))
    assert image is not None

    ocr = ChatOCR()
    ocr.initialize()
    result = ocr.find_helicopter_alert(image)

    assert result is None, "Should reject gather card without Explore header in Fast OCR"


def test_find_helicopter_alert_selects_newest_message_at_bottom() -> None:
    """When chat has an old message at top and a new one at bottom, select bottom."""
    ocr = ChatOCR()
    ocr._reader = _make_ocr_with_results(
        [
            # Old message at top (y=100)
            _make_block("Explore Treasure", x=10, y=100),
            _make_block("State 100 X100 Y100", x=10, y=140),
            # New message at bottom (y=600)
            _make_block("Explore Treasure", x=10, y=600),
            _make_block("State 742 X528 Y482", x=10, y=640),
        ]
    )
    image = __import__("numpy").zeros((700, 200, 3), dtype=__import__("numpy").uint8)
    result = ocr.find_helicopter_alert(image)
    assert result is not None
    assert result["coords_x"] == 528
    assert result["coords_y"] == 482
    assert result["click_y"] > 600, "Must click the bottom message, not the top one"


def test_find_helicopter_alert_rejects_decoupled_explore_and_state() -> None:
    """If 'Explore' is at y=100 and 'State X Y' is at y=500 (>160px), they must not pair."""
    ocr = ChatOCR()
    ocr._reader = _make_ocr_with_results(
        [
            _make_block("Explore Treasure", x=10, y=100),
            _make_block("State 100 X100 Y100", x=10, y=500),
        ]
    )
    image = __import__("numpy").zeros((600, 200, 3), dtype=__import__("numpy").uint8)
    result = ocr.find_helicopter_alert(image)
    assert result is None, "Must not pair Explore header with a distant State row"


def test_is_alliance_chat_open_detects_alliance() -> None:
    ocr = ChatOCR()
    ocr._reader = _make_ocr_with_results(
        [
            _make_block("World", x=10, y=10),
            _make_block("Alliance", x=100, y=10, conf=0.98),
            _make_block("Chat", x=200, y=10),
        ]
    )
    image = np.zeros((50, 300, 3), dtype=np.uint8)
    assert ocr.is_alliance_chat_open(image) is True


def test_is_alliance_chat_open_returns_false_when_missing() -> None:
    ocr = ChatOCR()
    ocr._reader = _make_ocr_with_results(
        [
            _make_block("World", x=10, y=10),
            _make_block("Notice", x=100, y=10),
        ]
    )
    image = np.zeros((50, 300, 3), dtype=np.uint8)
    assert ocr.is_alliance_chat_open(image) is False


def test_is_alliance_chat_open_respects_confidence() -> None:
    ocr = ChatOCR(min_confidence=0.5)
    ocr._reader = _make_ocr_with_results(
        [
            _make_block("Alliance", x=100, y=10, conf=0.3),
        ]
    )
    image = np.zeros((50, 300, 3), dtype=np.uint8)
    assert ocr.is_alliance_chat_open(image) is False
    assert ocr.is_alliance_chat_open(image, min_confidence=0.2) is True


def test_is_details_dialog_open_detects_details() -> None:
    ocr = ChatOCR()
    ocr._reader = _make_ocr_with_results(
        [
            _make_block("Details", x=50, y=10, conf=0.95),
        ]
    )
    image = np.zeros((50, 200, 3), dtype=np.uint8)
    assert ocr.is_details_dialog_open(image) is True


def test_is_details_dialog_open_returns_false_when_missing() -> None:
    ocr = ChatOCR()
    ocr._reader = _make_ocr_with_results(
        [
            _make_block("Explore Treasure", x=10, y=10),
            _make_block("Alliance Chat", x=100, y=10),
        ]
    )
    image = np.zeros((50, 200, 3), dtype=np.uint8)
    assert ocr.is_details_dialog_open(image) is False


def test_is_details_dialog_open_respects_confidence() -> None:
    ocr = ChatOCR(min_confidence=0.5)
    ocr._reader = _make_ocr_with_results(
        [
            _make_block("Details", x=50, y=10, conf=0.3),
        ]
    )
    image = np.zeros((50, 200, 3), dtype=np.uint8)
    assert ocr.is_details_dialog_open(image) is False
    assert ocr.is_details_dialog_open(image, min_confidence=0.2) is True


def test_timer_ocr_crop_diffing_cache() -> None:
    timer = TimerOCR()
    call_count = 0

    class MockReader:
        def readtext(self, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            return [([[0, 0], [10, 0], [10, 10], [0, 10]], "00:00:15", 0.9)]

    timer._reader = MockReader()
    image = np.ones((50, 100, 3), dtype=np.uint8) * 255

    # First call runs OCR
    res1 = timer.read_timer(image)
    assert res1 == 15
    assert call_count == 1

    # Second call with same image uses cached hash and doesn't invoke OCR
    res2 = timer.read_timer(image)
    assert res2 == 15
    assert call_count == 1

    # Call with modified image runs OCR again
    image_modified = image.copy()
    image_modified[0, 0] = 0
    res3 = timer.read_timer(image_modified)
    assert res3 == 15
    assert call_count == 2


def test_timer_ocr_winocr_fast_path(monkeypatch) -> None:
    timer = TimerOCR()
    timer._winocr_ok = True
    timer._winocr_lang = "en-US"

    import sys
    import types
    fake_winocr = types.ModuleType("winocr")
    called_winocr = False

    def fake_recognize(img, lang="en-US"):
        nonlocal called_winocr
        called_winocr = True
        return {"lines": [{"text": "00:02:30"}]}

    fake_winocr.recognize_cv2_sync = fake_recognize
    monkeypatch.setitem(sys.modules, "winocr", fake_winocr)

    # rapidocr mock that would fail if called
    timer._rapid = lambda *a, **kw: (_ for _ in ()).throw(AssertionError("RapidOCR should not be called"))

    image = np.zeros((40, 120, 3), dtype=np.uint8)
    result = timer.read_timer(image)
    assert result == 150
    assert called_winocr is True


def test_timer_ocr_winocr_fallback_to_rapid(monkeypatch) -> None:
    timer = TimerOCR()
    timer._winocr_ok = True
    timer._winocr_lang = "en-US"

    import sys
    import types
    fake_winocr = types.ModuleType("winocr")
    fake_winocr.recognize_cv2_sync = lambda img, lang="en-US": {"lines": [{"text": "garbage"}]}
    monkeypatch.setitem(sys.modules, "winocr", fake_winocr)

    called_rapid = False
    def fake_rapid(*args, **kwargs):
        nonlocal called_rapid
        called_rapid = True
        return [("00:00:45", 0.95)], None

    timer._rapid = fake_rapid

    image = np.zeros((40, 120, 3), dtype=np.uint8)
    result = timer.read_timer(image)
    assert result == 45
    assert called_rapid is True


def test_timer_ocr_rejects_truncated_winocr_reading(monkeypatch) -> None:
    """Regression test: WinOCR returns truncated '\"00:01' (missing seconds :27).

    It must NOT be parsed as 1s; it must be rejected and fall back to RapidOCR.
    """
    import sys
    import types

    timer = TimerOCR()
    timer._winocr_ok = True
    timer._winocr_lang = "pl"

    fake_winocr = types.ModuleType("winocr")
    # Simulate the exact bug from the log: WinOCR truncates the seconds
    fake_winocr.recognize_cv2_sync = lambda img, lang="pl": {"lines": [{"text": '"00:01'}]}
    monkeypatch.setitem(sys.modules, "winocr", fake_winocr)

    called_rapid = False

    def fake_rapid(*args, **kwargs):
        nonlocal called_rapid
        called_rapid = True
        return [("00:01:29", 0.95)], None

    timer._rapid = fake_rapid

    # Parser unit test: "00:01" must NOT return 1s
    assert TimerOCR._parse_time('"00:01') is None

    image = np.zeros((40, 120, 3), dtype=np.uint8)
    result = timer.read_timer(image)
    # Must fallback to RapidOCR and return 89s, never 1s!
    assert result == 89
    assert called_rapid is True


def test_find_helicopter_alert_rejects_blacklisted_cards(monkeypatch) -> None:
    """Ensure cards with State coords but headers like Bounty Missions, Truck,
    Empty Land, Share, Headquarters are immediately rejected without triggering alerts."""
    import sys
    import types

    ocr = ChatOCR()
    ocr._winocr_ok = True
    ocr._winocr_lang = "pl"

    for header in ["Bounty Missions", "Truck 3.14M", "Empty Land", "Share", "Headquarters", "Alliance Food"]:
        fake_lines = {
            "lines": [
                {"text": header, "words": [{"text": header, "bounding_rect": {"x": 10, "y": 20, "width": 80, "height": 15}}]},
                {"text": "Stałe 751 X:329 Y:451", "words": [{"text": "Stałe", "bounding_rect": {"x": 10, "y": 60, "width": 30, "height": 15}}]},
            ]
        }
        fake_winocr = types.ModuleType("winocr")
        fake_winocr.recognize_cv2_sync = lambda img, lang="pl", fl=fake_lines: fl
        monkeypatch.setitem(sys.modules, "winocr", fake_winocr)

        dummy_img = np.zeros((100, 300, 3), dtype=np.uint8)
        assert ocr.find_helicopter_alert(dummy_img) is None


def test_find_helicopter_alert_clicks_center_of_coordinates_line(monkeypatch) -> None:
    """Verify click coordinates target the center of the clickable State/X/Y coordinates hyperlink,
    not just the leftmost 'State' word."""
    import sys
    import types

    ocr = ChatOCR()
    ocr._winocr_ok = True
    ocr._winocr_lang = "pl"

    # Card layout: Explore header at y=10 (h=20), State line at y=90 (h=20)
    # Coordinates line: left=10, right=190 -> center_x = 100.0
    # Coordinates line: top=90, bottom=110 -> center_y = 100.0
    fake_lines = {
        "lines": [
            {
                "text": "Explore Treasure",
                "words": [{"text": "Explore", "bounding_rect": {"x": 10, "y": 10, "width": 180, "height": 20}}],
            },
            {
                "text": "Stałe 742 X:528 Y:482",
                "words": [
                    {"text": "Stałe", "bounding_rect": {"x": 10, "y": 90, "width": 40, "height": 20}},
                    {"text": "742", "bounding_rect": {"x": 55, "y": 90, "width": 30, "height": 20}},
                    {"text": "X:528", "bounding_rect": {"x": 90, "y": 90, "width": 45, "height": 20}},
                    {"text": "Y:482", "bounding_rect": {"x": 140, "y": 90, "width": 50, "height": 20}},
                ],
            },
        ]
    }
    fake_winocr = types.ModuleType("winocr")
    fake_winocr.recognize_cv2_sync = lambda img, lang="pl": fake_lines
    monkeypatch.setitem(sys.modules, "winocr", fake_winocr)

    dummy_img = np.zeros((120, 300, 3), dtype=np.uint8)
    res = ocr.find_helicopter_alert(dummy_img)
    assert res is not None
    assert res["coords_x"] == 528
    assert res["click_y"] == 60.0  # (120 / 2) = 60.0 (center of full alert card)
    assert res["click_x"] == 150.0  # (300 / 2) = 150.0 (center of full alert card)


# ── Wielojęzyczne testy słowników OCR (bez zależności od rapidocr) ──────────


def test_explore_re_matches_polish() -> None:
    assert _EXPLORE_RE.search("Eksploracja Skarbu")
    assert _EXPLORE_RE.search("znaleziono skarb")


def test_explore_re_matches_german_spanish_chinese() -> None:
    assert _EXPLORE_RE.search("Erkunden Schatz")
    assert _EXPLORE_RE.search("Explorar Tesoro")
    assert _EXPLORE_RE.search("探索 宝藏")


def test_explore_re_matches_arabic_thai_russian() -> None:
    assert _EXPLORE_RE.search("كنز")
    assert _EXPLORE_RE.search("สมบัติ")
    assert _EXPLORE_RE.search("сокровище")


def test_alliance_re_matches_multilingual() -> None:
    assert _ALLIANCE_RE.search("Alianza")  # hiszpański (jedno l)
    assert _ALLIANCE_RE.search("Alliance")
    assert _ALLIANCE_RE.search("Sojusz")
    assert _ALLIANCE_RE.search("Альянс")  # rosyjski
    assert _ALLIANCE_RE.search("联盟")  # chiński


def test_chat_re_matches_multilingual() -> None:
    assert _CHAT_RE.search("World")
    assert _CHAT_RE.search("Czat")
    assert _CHAT_RE.search("聊天")  # chiński
    assert _CHAT_RE.search("채팅")  # koreański


def test_details_re_matches_multilingual() -> None:
    assert _DETAILS_RE.search("Details")
    assert _DETAILS_RE.search("Szczegóły")
    assert _DETAILS_RE.search("Detalles")  # hiszpański
    assert _DETAILS_RE.search("细节")  # chiński


