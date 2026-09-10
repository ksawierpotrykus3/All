
from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

ROI_CHAT_ARROW = {
    "left": 58.0,
    "top": 81.5,
    "right": 63.5,
    "bottom": 92.0,
}


class ChatArrowDetector:
    def __init__(
        self,
        template_path: str | Path | None = None,
        threshold: float = 0.92,
    ) -> None:
        self.threshold = threshold
        self._template_bgr: np.ndarray | None = None
        self._template_mask: np.ndarray | None = None
        self._template_cache: dict[tuple[int, int], tuple[np.ndarray, np.ndarray | None]] = {}

        if template_path is None:
            import sys

            base_dirs: list[Path] = []
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                base_dirs.append(Path(meipass))
            if getattr(sys, "frozen", False):
                base_dirs.append(Path(sys.executable).resolve().parent)
            base_dirs.append(Path(__file__).resolve().parent.parent.parent)
            base_dirs.append(Path.cwd())

            candidates: list[Path] = []
            for b in base_dirs:
                candidates.extend(
                    [
                        b / "images" / "arrow.png",
                        b / "mvp" / "images" / "arrow.png",
                    ]
                )

            for cand in candidates:
                if cand.exists():
                    template_path = cand
                    break

        if template_path is not None and Path(template_path).exists():
            self.load_template(template_path)

    def load_template(self, path: str | Path) -> None:
        img = self._imread_unicode(str(path), cv2.IMREAD_UNCHANGED)
        if img is None:
            raise FileNotFoundError(f"Cannot load arrow template from {path}")
        if img.ndim == 3 and img.shape[2] == 4:
            self._template_bgr = img[:, :, :3]
            self._template_mask = img[:, :, 3]
        else:
            self._template_bgr = img if img.ndim == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            self._template_mask = None
        self._template_cache.clear()
        logger.debug(
            "ChatArrowDetector loaded template from %s (has_mask=%s, shape=%s)",
            path,
            self._template_mask is not None,
            self._template_bgr.shape,
        )

    @staticmethod
    def _imread_unicode(path: str, flags: int) -> np.ndarray | None:
        # cv2.imread silently returns None on Windows for non-ASCII paths; read
        # the file bytes via Python I/O and decode in memory instead.
        data = np.fromfile(path, dtype=np.uint8)
        if data.size == 0:
            return None
        return cv2.imdecode(data, flags)

    def find_arrow(
        self,
        frame: np.ndarray,
        roi_rect: tuple[int, int, int, int] | None = None,
        threshold: float | None = None,
    ) -> tuple[int, int, float] | None:
        if self._template_bgr is None:
            return None

        thresh = threshold if threshold is not None else self.threshold
        fh, fw = frame.shape[:2]

        if roi_rect is not None:
            left, top, right, bottom = roi_rect
            left = max(0, min(fw, left))
            right = max(0, min(fw, right))
            top = max(0, min(fh, top))
            bottom = max(0, min(fh, bottom))
            if right <= left or bottom <= top:
                return None
            search_area = frame[top:bottom, left:right]
            offset_x, offset_y = left, top
        else:
            search_area = frame
            offset_x, offset_y = 0, 0

        sh, sw = search_area.shape[:2]
        if sh < 4 or sw < 4:
            return None

        orig_h, orig_w = self._template_bgr.shape[:2]
        base_scale = fh / 1075.0 if fh > 50 else 1.0
        scales = (
            [base_scale * f for f in (0.90, 0.95, 1.0, 1.05, 1.10)] if base_scale > 0.1 else [1.0]
        )

        best_match: tuple[int, int, float] | None = None

        for s in scales:
            tw = max(4, int(round(orig_w * s)))
            th = max(4, int(round(orig_h * s)))

            if sh < th or sw < tw:
                continue

            cache_key = (tw, th)
            cached = self._template_cache.get(cache_key)
            if cached is not None:
                res_bgr, res_mask = cached
            else:
                interp = cv2.INTER_AREA if s < 1.0 else cv2.INTER_CUBIC
                res_bgr = cv2.resize(self._template_bgr, (tw, th), interpolation=interp)
                if self._template_mask is not None:
                    res_mask = cv2.resize(self._template_mask, (tw, th), interpolation=interp)
                    _, res_mask = cv2.threshold(res_mask, 127, 255, cv2.THRESH_BINARY)
                else:
                    res_mask = None
                self._template_cache[cache_key] = (res_bgr, res_mask)

            if res_mask is not None:
                res = cv2.matchTemplate(search_area, res_bgr, cv2.TM_SQDIFF_NORMED, mask=res_mask)
                min_val, _, min_loc, _ = cv2.minMaxLoc(res)
                score = 1.0 - float(min_val)
                best_loc = min_loc
            else:
                res = cv2.matchTemplate(search_area, res_bgr, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)
                score = float(max_val)
                best_loc = max_loc

            if score >= thresh:
                patch = search_area[best_loc[1] : best_loc[1] + th, best_loc[0] : best_loc[0] + tw]
                if self._template_mask is not None:
                    mean_b, _, mean_r = cv2.mean(patch, mask=res_mask)[:3]
                else:
                    mean_b, _, mean_r = cv2.mean(patch)[:3]

                warmth = mean_r - mean_b
                if warmth > 8.0:
                    continue

                if best_match is None or score > best_match[2]:
                    center_x = offset_x + best_loc[0] + tw // 2
                    center_y = offset_y + best_loc[1] + th // 2
                    best_match = (center_x, center_y, score)

        if best_match is not None:
            logger.debug(
                "Chat arrow found at (%d, %d) with score %.4f (scale ~%.3f)",
                best_match[0],
                best_match[1],
                best_match[2],
                base_scale,
            )

        return best_match
