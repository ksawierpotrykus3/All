from __future__ import annotations

import contextlib
import logging
import re
import threading

# CRITICAL on Windows: onnxruntime must be loaded BEFORE winrt / WinOCR COM threads
# to prevent onnxruntime_pybind11_state DLL initialization collision.
with contextlib.suppress(Exception):
    import onnxruntime  # noqa: F401


import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Wielojęzyczne warianty słów oznaczających "skarb / eksploracja" (nagłówek alertu
# helikoptera). Współrzędne "X:### Y:###" są zawsze zapisywane cyframi łacińskimi,
# więc główna detekcja liczb działa niezależnie od języka interfejsu gry.
# Uwaga: to słowa kluczowe nagłówka karty helikoptera — gather/zbiórka ich NIE zawiera,
# dzięki czemu obie karty dają się odróżnić bez zależności od konkretnego języka.
_EXPLORE_WORDS = (
    # łacińskie (angielski, francuski, hiszpański, portugalski, włoski)
    "explor", "treas", "reasure", "trésor", "tesor", "tesour", "esplor",
    "erkund", "schatz", "hazine", "harta", "khám phá", "kho báu",
    # polski (defensywnie — gra może dostać wersję PL)
    "eksplor", "skarb", "łup", "zbadaj",
    # rosyjski / ukraiński
    "клад", "сокровищ", "развед", "скарб",
    # CJK
    "宝", "寶", "宝藏", "寶藏", "宝物", "보물", "탐험", "探検", "探索", "探險",
    # arabski / tajski
    "كنز", "استكشاف", "สมบัติ", "สำรวจ",
)
_EXPLORE_RE = re.compile("|".join(re.escape(w) for w in _EXPLORE_WORDS), re.IGNORECASE)

# Zakładka czatu sojuszu (Alliance) — wielojęzycznie. Krytyczne: po hiszpańsku
# "Alianza" (jedno l), po rosyjsku "Альянс", po chińsku "联盟" itd.
_ALLIANCE_WORDS = (
    # łacińskie
    "allian", "alian", "sojusz", "aliad", "aliance", "alliance", "aliança",
    "aliata", "aliate",
    # rosyjski / ukraiński
    "альянс", "союз", "альянсу",
    # CJK
    "联盟", "同盟", "聯合", "聯合軍", "동맹", "연맹",
    # arabski
    "تحالف",
    # turecki
    "ittifak", "müttefik",
    # wietnamski / tajski
    "liên minh", "đồng minh", "พันธมิตร",
)
_ALLIANCE_RE = re.compile("|".join(re.escape(w) for w in _ALLIANCE_WORDS), re.IGNORECASE)

# Ogólne zakładki okna czatu.
_CHAT_WORDS = (
    "chat", "world", "state", "group", "czat", "świat", "grupa", "talk",
    "聊天", "世界", "州", "聊天室", "チャット", "ワールド", "채팅", "월드",
    "دردشة", "sohbet", "trò chuyện",
)
_CHAT_RE = re.compile("|".join(re.escape(w) for w in _CHAT_WORDS), re.IGNORECASE)

# Dialog "Details"/"Szczegóły".
_DETAILS_WORDS = (
    "details", "szczeg", "detall", "dettagli", "detalh", "detalles",
    "детал", "细节", "詳細", "세부", "تفاصيل", "detay", "chi tiết",
)
_DETAILS_RE = re.compile("|".join(re.escape(w) for w in _DETAILS_WORDS), re.IGNORECASE)


def _rapid_result_text(entry) -> str:
    """Wyciąga tekst z wyniku RapidOCR.

    rapidocr-onnxruntime 1.2.3 zwraca [bbox, text, score] (tekst na indeksie 1);
    starsze mocki w testach używają 2-elementowej krotki (text, score).
    """
    if isinstance(entry, (list, tuple)):
        if len(entry) >= 3:
            return str(entry[1])
        if len(entry) == 2:
            return str(entry[0])
    return ""

# Global singletons for OCR engines
_rapid_engine = None
_rapid_engine_lock = threading.Lock()

_winocr_initialized = False
_winocr_available = False
_winocr_lang: str | None = None
_winocr_lock = threading.Lock()


def _get_shared_rapidocr():
    """Lazy-initialize singleton RapidOCR engine (ONNX Runtime)."""
    global _rapid_engine
    with _rapid_engine_lock:
        if _rapid_engine is None:
            from rapidocr_onnxruntime import RapidOCR

            _rapid_engine = RapidOCR(
                use_angle_cls=False,
                intra_op_num_threads=2,
                inter_op_num_threads=1,
            )
            logger.info("RapidOCR (ONNX Runtime) engine initialized (threads limited to 2)")
        return _rapid_engine


def _get_winocr_status() -> tuple[bool, str | None]:
    """Check and return availability of native Windows.Media.Ocr."""
    global _winocr_initialized, _winocr_available, _winocr_lang
    with _winocr_lock:
        if not _winocr_initialized:
            _winocr_initialized = True
            try:
                from winrt.windows.media.ocr import OcrEngine

                langs = [lang.language_tag for lang in OcrEngine.available_recognizer_languages]
                logger.debug("Windows.Media.Ocr available languages: %s", langs)
                if "en-US" in langs:
                    _winocr_lang = "en-US"
                    _winocr_available = True
                elif langs:
                    _winocr_lang = langs[0]
                    _winocr_available = True
                else:
                    _winocr_available = False
                    _winocr_lang = None
            except Exception as exc:
                logger.warning("Windows.Media.Ocr not available: %s", exc)
                _winocr_available = False
                _winocr_lang = None
        return _winocr_available, _winocr_lang




class ImagePreprocessor:
    @staticmethod
    def upscale(image: np.ndarray, factor: int = 2) -> np.ndarray:
        return cv2.resize(image, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)


def _get_exact_alert_card_center(
    image: np.ndarray, y_anchor: float, fallback_x: float, fallback_y: float
) -> tuple[float, float]:
    try:
        ih, iw = image.shape[:2]
        if iw < 350 and ih < 150:
            # Already a tightly cropped alert card (e.g. 303x105)
            return float(iw / 2.0), float(ih / 2.0)

        y1 = max(0, int(y_anchor - 80))
        y2 = min(ih, int(y_anchor + 80))
        roi = image[y1:y2, :]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        lower_orange = np.array([5, 110, 110])
        upper_orange = np.array([25, 255, 255])
        mask = cv2.inRange(hsv, lower_orange, upper_orange)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        best_box = None
        best_area = 0
        for c in contours:
            bx, by, bw, bh = cv2.boundingRect(c)
            if bw > 140 and bh > 40:
                area = bw * bh
                if area > best_area:
                    best_area = area
                    best_box = (bx, y1 + by, bw, bh)

        if best_box:
            bx, by, bw, bh = best_box
            return float(bx + bw / 2.0), float(by + bh / 2.0)
    except Exception:
        pass
    return fallback_x, fallback_y


class ChatOCR:
    """High-speed Chat OCR using native WinOCR (13-17 ms) with RapidOCR ONNX fallback."""

    def __init__(self, min_confidence: float = 0.3) -> None:
        self._min_confidence = min_confidence
        self._reader = None  # Backward-compatibility for unit test mocks
        self._rapid = None
        self._winocr_ok = False
        self._winocr_lang: str | None = None

    def initialize(self) -> None:
        self._winocr_ok, self._winocr_lang = _get_winocr_status()
        self._rapid = _get_shared_rapidocr()
        logger.info(
            "Fast ChatOCR initialized (WinOCR available: %s [lang=%s], RapidOCR active)",
            self._winocr_ok,
            self._winocr_lang,
        )

    @staticmethod
    def _parse_coords(text: str) -> tuple[int, int] | None:
        match = re.search(r"(\d{1,4})\s*[,:;]\s*(\d{1,4})", text)
        if match:
            return (int(match.group(1)), int(match.group(2)))
        return None

    def find_helicopter_alert(self, image: np.ndarray) -> dict | None:
        """Find helicopter alert in chat ROI.

        Uses fast WinOCR first (~17 ms), falling back to RapidOCR (~180 ms).
        Returns dict with coords and click target if detected.
        """
        # Support monkey-patched _reader in unit tests
        if self._reader is not None:
            results = self._reader.readtext(
                image,
                allowlist="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz: -",
                detail=1,
            )
            if not results:
                return None
            results = [r for r in results if r[2] >= self._min_confidence]
            if not results:
                return None

            lines: list[list] = []
            sorted_results = sorted(results, key=lambda r: (r[0][0][1] + r[0][2][1]) / 2)
            for item in sorted_results:
                bbox, text, conf = item
                center_y = (bbox[0][1] + bbox[2][1]) / 2
                matched_line = False
                for line in lines:
                    line_center_y = (line[0][0][0][1] + line[0][0][2][1]) / 2
                    if abs(center_y - line_center_y) < 8:
                        line.append(item)
                        matched_line = True
                        break
                if not matched_line:
                    lines.append([item])

            explore_pattern = _EXPLORE_RE
            # Współrzędne "X:### Y:###" są zawsze łacińskie, niezależnie od języka
            # interfejsu gry — dlatego NIE wymagamy już słowa "State".
            heli_pattern = re.compile(
                r"(\d{1,4})[^\d]*X[^\d]*(\d+).*?[YVl][^\d]*(\d+)", re.IGNORECASE
            )

            for line_idx in range(len(lines) - 1, -1, -1):
                line_items = lines[line_idx]
                line_text = " ".join(item[1] for item in line_items)
                match = heli_pattern.search(line_text)
                if not match:
                    continue

                state_center_y = (
                    min(item[0][0][1] for item in line_items)
                    + max(item[0][2][1] for item in line_items)
                ) / 2

                card_has_explore = False
                for prev_idx in range(line_idx, -1, -1):
                    prev_line_items = lines[prev_idx]
                    prev_center_y = (
                        min(item[0][0][1] for item in prev_line_items)
                        + max(item[0][2][1] for item in prev_line_items)
                    ) / 2
                    dy = state_center_y - prev_center_y
                    if dy > 160:
                        break
                    prev_text = " ".join(item[1] for item in prev_line_items)
                    if explore_pattern.search(prev_text):
                        card_has_explore = True
                        break

                if not card_has_explore:
                    continue

                state_num = int(match.group(1))
                coord_x = int(match.group(2))
                coord_y = int(match.group(3))

                min_x = min(item[0][0][0] for item in line_items)
                max_x = max(item[0][1][0] for item in line_items)
                min_y = min(item[0][0][1] for item in line_items)
                max_y = max(item[0][2][1] for item in line_items)

                return {
                    "text": line_text,
                    "coords_x": coord_x,
                    "coords_y": coord_y,
                    "click_x": float((min_x + max_x) / 2),
                    "click_y": float((min_y + max_y) / 2),
                }

            return None

        if self._rapid is None:
            self.initialize()

        explore_pattern = _EXPLORE_RE
        # Współrzędne "X:### Y:###" są zawsze łacińskie, niezależnie od języka gry.
        heli_pattern = re.compile(
            r"(\d{1,4})[^\d]*X[^\d]*(\d+).*?[YVl][^\d]*(\d+)", re.IGNORECASE
        )
        blacklist_pattern = re.compile(
            r"(?:Bounty\s*Missions?|Truck|Empty\s*Land|Share|Headquarters|Alliance\s*(?:Food|Iron|Oil|Lumber))",
            re.IGNORECASE,
        )

        target_image: np.ndarray | None = None
        y_offset = 0

        # 1. Try ultra-fast native WinOCR (13-17 ms)
        if self._winocr_ok and self._winocr_lang:
            try:
                import winocr

                win_res = winocr.recognize_cv2_sync(image, lang=self._winocr_lang)
                if isinstance(win_res, dict) and "lines" in win_res:
                    lines = win_res["lines"]
                    parsed_lines = []
                    for line in lines:
                        l_text = line.get("text", "")
                        words = line.get("words", [])
                        if words and "bounding_rect" in words[0]:
                            rect = words[0]["bounding_rect"]
                            y_pos = float(rect.get("y", 0) + rect.get("height", 0) / 2)
                        else:
                            y_pos = 0.0
                        parsed_lines.append((y_pos, l_text, line))

                    parsed_lines.sort(key=lambda x: x[0])

                    for idx in range(len(parsed_lines) - 1, -1, -1):
                        state_y, l_text, line = parsed_lines[idx]
                        m = heli_pattern.search(l_text)
                        if not m:
                            continue

                        # Check preceding lines within 90px for Explore header and blacklist items
                        has_explore = False
                        is_blacklisted = False
                        explore_line = None

                        for prev_idx in range(idx - 1, -1, -1):
                            prev_y, prev_text, p_line = parsed_lines[prev_idx]
                            dy = state_y - prev_y
                            if dy > 90:
                                break
                            if dy > 0:
                                if blacklist_pattern.search(prev_text):
                                    is_blacklisted = True
                                    break
                                if explore_pattern.search(prev_text):
                                    has_explore = True
                                    explore_line = p_line
                                    break

                        if is_blacklisted or not has_explore or explore_line is None:
                            continue

                        state_num = int(m.group(1))
                        coord_x = int(m.group(2))
                        coord_y = int(m.group(3))

                        # Target click in exact center of entire alert card
                        exp_words = explore_line.get("words", [])
                        state_words = line.get("words", [])
                        if exp_words and state_words:
                            card_top = min(float(w["bounding_rect"].get("y", 0)) for w in exp_words if "bounding_rect" in w)
                            card_bottom = max(
                                float(w["bounding_rect"].get("y", 0) + w["bounding_rect"].get("height", 0))
                                for w in state_words if "bounding_rect" in w
                            )
                            all_card_words = exp_words + state_words
                            card_left = min(float(w["bounding_rect"].get("x", 0)) for w in all_card_words if "bounding_rect" in w)
                            card_right = max(
                                float(w["bounding_rect"].get("x", 0) + w["bounding_rect"].get("width", 0))
                                for w in all_card_words if "bounding_rect" in w
                            )
                            fb_x = float((card_left + card_right) / 2)
                            fb_y = float((card_top + card_bottom) / 2)
                        else:
                            fb_x = float(image.shape[1] / 2)
                            fb_y = float(image.shape[0] / 2)

                        click_x, click_y = _get_exact_alert_card_center(image, state_y, fb_x, fb_y)

                        logger.info(
                            "Helicopter alert detected (WinOCR): State %d X:%d Y:%d (click center at %.0f,%.0f)",
                            state_num, coord_x, coord_y, click_x, click_y,
                        )
                        return {
                            "text": l_text,
                            "coords_x": coord_x,
                            "coords_y": coord_y,
                            "click_x": click_x,
                            "click_y": click_y,
                        }

                    # Fast dual-gate verification before skipping RapidOCR:
                    # Specific helicopter cues (never generic words like 'spot' or 'troop').
                    # Wielojęzyczne — musi obejmować wszystkie języki gry, inaczej
                    # karta w języku innym niż angielski zostanie błędnie odrzucona.
                    hint_pattern = _EXPLORE_RE
                    hint_matches = [
                        pl for pl in parsed_lines
                        if hint_pattern.search(pl[1]) and not blacklist_pattern.search(pl[1])
                    ]
                    has_text_hint = len(hint_matches) > 0

                    if not has_text_hint:
                        # WinOCR nie znalazł tekstowych poszlak helikoptera. Dwie możliwości:
                        #  1) czysty czat bez alertu → szybkie wyjście (~30 ms);
                        #  2) alert w alfabecie niełacińskim (chiński/rosyjski/arabski),
                        #     który WinOCR zwrócił jako "???" → MUSIMY odpalić RapidOCR.
                        # Rozróżniamy je kolorem: duża pomarańczowa karta = podejrzenie alertu.
                        has_orange = False
                        if image is not None and image.size > 0:
                            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
                            mask = cv2.inRange(hsv, np.array([5, 100, 100]), np.array([25, 255, 255]))
                            has_orange = bool(np.count_nonzero(mask) >= 10000)
                        if not has_orange:
                            # Czysty czat bez alertu — definitive clean exit.
                            return None
                        # Pomarańczowa karta obecna — pozwól RapidOCR (wielojęzycznemu)
                        # sprawdzić cały obraz, zamiast ucinać detekcję.
                        target_image = image
                        y_offset = 0

                    if has_text_hint:
                        # If hint text is present, narrow RapidOCR ROI to candidate area (+/- 140px)
                        min_hint_y = min(pl[0] for pl in hint_matches)
                        max_hint_y = max(pl[0] for pl in hint_matches)
                        y1 = max(0, int(min_hint_y - 60))
                        y2 = min(image.shape[0], int(max_hint_y + 140))
                        target_image = image[y1:y2, :]
                        y_offset = y1
            except Exception as exc:
                logger.debug("WinOCR find_helicopter_alert attempt failed: %s", exc)

        # Fallback to RapidOCR ONNX: only if WinOCR was unavailable, failed, or found candidate hint
        if target_image is None:
            has_orange = False
            if image is not None and image.size > 0:
                hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
                mask = cv2.inRange(hsv, np.array([5, 100, 100]), np.array([25, 255, 255]))
                has_orange = bool(np.count_nonzero(mask) >= 10000)

            if not has_orange:
                return None
            target_image = image
            y_offset = 0

        rapid_results, _ = self._rapid(target_image)
        if not rapid_results:
            return None

        # Group rapid blocks into lines by Y coordinate
        sorted_items = sorted(rapid_results, key=lambda r: (r[0][0][1] + r[0][2][1]) / 2)
        lines_rapid: list[list] = []
        for item in sorted_items:
            box, text, score = item
            cy = (box[0][1] + box[2][1]) / 2
            matched = False
            for line in lines_rapid:
                line_cy = sum((it[0][0][1] + it[0][2][1]) / 2 for it in line) / len(line)
                if abs(cy - line_cy) < 14:
                    line.append(item)
                    matched = True
                    break
            if not matched:
                lines_rapid.append([item])

        # Within each line, sort items from left to right (X coordinate)
        for line in lines_rapid:
            line.sort(key=lambda it: it[0][0][0])

        for idx in range(len(lines_rapid) - 1, -1, -1):
            line = lines_rapid[idx]
            line_text = " ".join(it[1] for it in line)
            m = heli_pattern.search(line_text)
            if not m:
                continue

            line_y = sum((it[0][0][1] + it[0][2][1]) / 2 for it in line) / len(line)

            # Check preceding lines within 160px for Explore header and blacklist items
            has_explore = False
            is_blacklisted = False
            explore_line_items = None

            for prev_idx in range(idx - 1, -1, -1):
                prev_line = lines_rapid[prev_idx]
                prev_line_y = sum((it[0][0][1] + it[0][2][1]) / 2 for it in prev_line) / len(prev_line)
                dy = line_y - prev_line_y
                if dy > 90:
                    break
                if dy > 0:
                    prev_text = " ".join(it[1] for it in prev_line)
                    if blacklist_pattern.search(prev_text):
                        is_blacklisted = True
                        break
                    if explore_pattern.search(prev_text):
                        has_explore = True
                        explore_line_items = prev_line
                        break

            if is_blacklisted or not has_explore or explore_line_items is None:
                continue

            coord_x = int(m.group(2))
            coord_y = int(m.group(3))

            # Target click in exact geometric center of entire alert card
            card_top = min(it[0][0][1] for it in explore_line_items)
            card_bottom = max(it[0][2][1] for it in line)
            all_items = explore_line_items + line
            card_left = min(it[0][0][0] for it in all_items)
            card_right = max(it[0][1][0] for it in all_items)

            fb_x = float((card_left + card_right) / 2)
            fb_y = float((card_top + card_bottom) / 2) + y_offset
            click_x, click_y = _get_exact_alert_card_center(
                image, fb_y, fb_x, fb_y
            )

            logger.info(
                "Helicopter alert detected (RapidOCR): State %s X:%d Y:%d (click center at %.0f,%.0f)",
                m.group(1), coord_x, coord_y, click_x, click_y,
            )
            return {
                "text": line_text,
                "coords_x": coord_x,
                "coords_y": coord_y,
                "click_x": click_x,
                "click_y": click_y,
            }

        return None

    def is_alliance_chat_open(self, image: np.ndarray, min_confidence: float | None = None) -> bool:
        """Check if Alliance chat tab is open/active."""
        conf_threshold = min_confidence if min_confidence is not None else self._min_confidence
        pattern = _ALLIANCE_RE

        if self._reader is not None:
            results = self._reader.readtext(
                image,
                allowlist="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz: -",
                detail=1,
            )
            if not results:
                return False
            for _bbox, text, conf in results:
                if conf >= conf_threshold and pattern.search(text):
                    return True
            return False

        if self._rapid is None:
            self.initialize()

        # 1. Fast WinOCR (~13 ms)
        if self._winocr_ok and self._winocr_lang:
            try:
                import winocr

                win_res = winocr.recognize_cv2_sync(image, lang=self._winocr_lang)
                if isinstance(win_res, dict) and "lines" in win_res:
                    return any(pattern.search(line.get("text", "")) for line in win_res["lines"])
            except Exception as exc:
                logger.debug("WinOCR is_alliance_chat_open failed: %s", exc)

        # 2. Fallback to RapidOCR
        rapid_results, _ = self._rapid(image)
        if rapid_results:
            for _box, text, _score in rapid_results:
                if pattern.search(text):
                    return True

        return False

    def is_chat_window_open(self, image: np.ndarray, min_confidence: float | None = None) -> bool:
        """Check if chat window tab bar is visible."""
        conf_threshold = min_confidence if min_confidence is not None else self._min_confidence
        pattern = _CHAT_RE

        if self._reader is not None:
            results = self._reader.readtext(
                image,
                allowlist="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz: -",
                detail=1,
            )
            if not results:
                return False
            for _bbox, text, conf in results:
                if conf >= conf_threshold and pattern.search(text):
                    return True
            return False

        if self._rapid is None:
            self.initialize()

        # 1. Fast WinOCR
        if self._winocr_ok and self._winocr_lang:
            try:
                import winocr

                win_res = winocr.recognize_cv2_sync(image, lang=self._winocr_lang)
                if isinstance(win_res, dict) and "lines" in win_res:
                    return any(pattern.search(line.get("text", "")) for line in win_res["lines"])
            except Exception as exc:
                logger.debug("WinOCR is_chat_window_open failed: %s", exc)

        # 2. Fallback to RapidOCR
        rapid_results, _ = self._rapid(image)
        if rapid_results:
            for _box, text, _score in rapid_results:
                if pattern.search(text):
                    return True

        return False

    def is_details_dialog_open(self, image: np.ndarray, min_confidence: float | None = None) -> bool:
        """Check if target details dialog is open."""
        conf_threshold = min_confidence if min_confidence is not None else self._min_confidence
        pattern = _DETAILS_RE

        if self._reader is not None:
            results = self._reader.readtext(
                image,
                allowlist="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz: -",
                detail=1,
            )
            if not results:
                return False
            for _bbox, text, conf in results:
                if conf >= conf_threshold and pattern.search(text):
                    return True
            return False

        if self._rapid is None:
            self.initialize()

        # 1. Fast WinOCR
        if self._winocr_ok and self._winocr_lang:
            try:
                import winocr

                win_res = winocr.recognize_cv2_sync(image, lang=self._winocr_lang)
                if isinstance(win_res, dict) and "lines" in win_res:
                    return any(pattern.search(line.get("text", "")) for line in win_res["lines"])
            except Exception as exc:
                logger.debug("WinOCR is_details_dialog_open failed: %s", exc)

        # 2. Fallback to RapidOCR
        rapid_results, _ = self._rapid(image)
        if rapid_results:
            for _box, text, _score in rapid_results:
                if pattern.search(text):
                    return True

        return False


class TimerOCR:
    """Ultra-fast Timer OCR using RapidOCR Recognition-Only (~39 ms) on fixed ROI."""

    def __init__(
        self,
        upscale_factor: int = 2,
        white_mask_factor: int = 2,
        binarize_block: int = 11,
        binarize_c: int = 2,
        psm: int = 7,
        min_confidence: float = 0.3,
    ) -> None:
        self._upscale_factor = upscale_factor
        self._white_mask_factor = white_mask_factor
        self._binarize_block = binarize_block
        self._binarize_c = binarize_c
        self._psm = psm
        self._min_confidence = min_confidence
        self._reader = None  # Backward-compatibility for unit test mocks
        self._rapid = None
        self._winocr_ok = False
        self._winocr_lang: str | None = None
        self._last_sample: np.ndarray | None = None
        self._last_read_result: int | None = None

    def initialize(self) -> None:
        self._winocr_ok, self._winocr_lang = _get_winocr_status()
        self._rapid = _get_shared_rapidocr()
        logger.info(
            "Fast TimerOCR initialized (WinOCR available: %s [lang=%s], RapidOCR active)",
            self._winocr_ok,
            self._winocr_lang,
        )

    @staticmethod
    def _parse_time(text: str) -> int | None:
        # Full HH:MM:SS format (e.g. "00:01:29", "00:00:05", "01:20:15") - standard for helicopter timer
        match = re.search(r"(?:^|[^\d:])(\d{1,2}):(\d{2}):(\d{2})", text)
        if match:
            h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
            if m <= 59 and s <= 59:
                return h * 3600 + m * 60 + s

        # Two-part MM:SS format (e.g. "01:30" -> 90s, "02:45" -> 165s)
        match = re.search(r"(?:^|[^\d:])(\d{1,2}):(\d{2})(?:[^\d:]|$)", text)
        if match:
            first, second = int(match.group(1)), int(match.group(2))
            if first <= 59 and second <= 59:
                # Truncation guard: helicopter timer for <=59s ALWAYS shows "00:00:SS".
                # A reading of "00:01" or "00:05" is a truncated "00:01:SS" (>=60s) missing seconds,
                # NOT 1s/5s! Reject to prevent premature spam triggers.
                if first == 0 and second < 10:
                    return None
                return first * 60 + second

        match = re.search(r"(?:^|[^\d:])(\d{1,4})\s*s(?:[^\w]|$)", text, re.I)
        if match:
            return int(match.group(1))
        return None

    def read_timer(self, image: np.ndarray, *, max_passes: int = 4) -> int | None:
        if image is None or image.size == 0:
            return None
        # Downsample (stride 2) to avoid copying the full buffer to Python bytes, then
        # compare the full sample deterministically (array equality) rather than relying
        # on a metadata hash, which can collide and serve a stale timer read.
        sample = image[::2, ::2] if image.ndim >= 2 else image
        if self._last_sample is not None and np.array_equal(sample, self._last_sample):
            return self._last_read_result

        result = self._read_timer_uncached(image, max_passes=max_passes)
        self._last_sample = sample.copy()
        self._last_read_result = result
        return result

    def _read_timer_uncached(self, image: np.ndarray, *, max_passes: int = 4) -> int | None:
        # Support monkey-patched _reader in unit tests
        if self._reader is not None:
            results = self._reader.readtext(image, allowlist="0123456789:", detail=1)
            for _bbox, text, _conf in results:
                total = self._parse_time(text.strip())
                if total is not None:
                    return total
            return None

        # Pass 0: Ultra-fast native WinOCR (~8-15 ms)
        # STRICT: WinOCR is accepted ONLY if it recognizes full HH:MM:SS format (3 segments).
        # Truncated readings like "00:01" (missing seconds) are rejected and fall back to RapidOCR.
        if self._winocr_ok and self._winocr_lang:
            try:
                import winocr

                win_res = winocr.recognize_cv2_sync(image, lang=self._winocr_lang)
                if isinstance(win_res, dict) and "lines" in win_res:
                    for line in win_res["lines"]:
                        txt = line.get("text", "")
                        if re.search(r"(?:^|[^\d:])\d{1,2}:\d{2}:\d{2}", txt):
                            sec = self._parse_time(txt)
                            if sec is not None:
                                logger.debug("Timer OCR (WinOCR fast-path): '%s' -> %d seconds", txt, sec)
                                return sec
            except Exception as exc:
                logger.debug("WinOCR timer read failed, falling back to RapidOCR: %s", exc)

        if self._rapid is None:
            self.initialize()

        # Pass 1: HSV white mask + RapidOCR recognition-only (~25-32 ms!)
        # Per AGENTS.md Rule 16: RapidOCR rec-only guarantees 100% precision on full HH:MM:SS without truncations.
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        white_mask = cv2.inRange(hsv, np.array([0, 0, 200]), np.array([180, 50, 255]))
        white_up = cv2.resize(white_mask, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        white_3ch = cv2.cvtColor(white_up, cv2.COLOR_GRAY2BGR)

        res_rec, _ = self._rapid(white_3ch, use_det=False, use_cls=False)
        if res_rec:
            full_txt = " ".join(_rapid_result_text(r) for r in res_rec)
            sec = self._parse_time(full_txt)
            if sec is not None:
                logger.debug("Timer OCR (rapidocr rec-only): '%s' -> %d seconds", full_txt, sec)
                return sec

        # Pass 2: Raw upscale 2x recognition-only
        if max_passes >= 2:
            up2 = cv2.resize(image, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            res_rec2, _ = self._rapid(up2, use_det=False, use_cls=False)
            if res_rec2:
                full_txt2 = " ".join(_rapid_result_text(r) for r in res_rec2)
                sec2 = self._parse_time(full_txt2)
                if sec2 is not None:
                    logger.debug("Timer OCR (rapidocr 2x rec): '%s' -> %d seconds", full_txt2, sec2)
                    return sec2

        # Pass 3: Full detection + recognition fallback on raw image (handles colored/green text and full frames)
        if max_passes >= 3:
            res_full, _ = self._rapid(image, use_det=True, use_cls=False)
            if res_full:
                for _box, text, _score in res_full:
                    sec3 = self._parse_time(text)
                    if sec3 is not None:
                        logger.debug("Timer OCR (rapidocr full): '%s' -> %d seconds", text, sec3)
                        return sec3

        return None
