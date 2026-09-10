"""OpenCV template matching and image preprocessing."""
import logging

import cv2
import numpy as np

DEFAULT_MULTI_SCALES: tuple[float, ...] = (0.8, 0.9, 1.0, 1.1, 1.2)

logger = logging.getLogger(__name__)


def _to_grayscale(image: np.ndarray) -> np.ndarray:
    """Convert BGR to grayscale; passthrough if already single-channel."""
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image


class TemplateDetector:
    def __init__(self, threshold: float = 0.85) -> None:
        self.threshold = threshold
        self._templates: dict[str, np.ndarray] = {}

    def get_template(self, name: str) -> np.ndarray | None:
        """Public accessor for loaded templates."""
        return self._templates.get(name)

    def load_template(self, name: str, path: str) -> np.ndarray:
        template = cv2.imread(path, cv2.IMREAD_COLOR)
        if template is None:
            raise FileNotFoundError(f"Template not found: {path}")
        self._templates[name] = template
        logger.debug(
            "load_template name=%s path=%s width=%d height=%d",
            name,
            path,
            template.shape[1],
            template.shape[0],
        )
        return template

    def find(
        self,
        frame: np.ndarray,
        template: np.ndarray,
        threshold: float | None = None,
    ) -> tuple[int, int] | None:
        thresh = threshold if threshold is not None else self.threshold
        result = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val < thresh:
            return None
        h, w = template.shape[:2]
        center_x = max_loc[0] + w // 2
        center_y = max_loc[1] + h // 2
        logger.debug("Template match: val=%.3f at (%d,%d)", max_val, center_x, center_y)
        return (center_x, center_y)

    def find_named(
        self,
        frame: np.ndarray,
        name: str,
        threshold: float | None = None,
    ) -> tuple[int, int] | None:
        logger.debug("find_named name=%s threshold=%s", name, threshold)
        if name not in self._templates:
            raise FileNotFoundError(f"Template '{name}' not loaded")
        return self.find(frame, self._templates[name], threshold)

    def find_multi_scale(
        self,
        frame: np.ndarray,
        template: np.ndarray,
        scales: tuple[float, ...] | None = None,
        threshold: float | None = None,
    ) -> tuple[int, int, float] | None:
        if scales is None:
            scales = DEFAULT_MULTI_SCALES
        actual_threshold = threshold if threshold is not None else self.threshold
        best_val = 0.0
        best_loc: tuple[int, int, float] | None = None
        gray_frame = _to_grayscale(frame)
        gray_template = _to_grayscale(template)
        for scale in scales:
            scaled = cv2.resize(gray_template, None, fx=scale, fy=scale)
            if scaled.shape[0] > gray_frame.shape[0] or scaled.shape[1] > gray_frame.shape[1]:
                continue
            logger.debug(
                "find_multi_scale scale=%s width=%d height=%d",
                scale,
                scaled.shape[1],
                scaled.shape[0],
            )
            result = cv2.matchTemplate(gray_frame, scaled, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val > best_val and max_val >= actual_threshold:
                best_val = max_val
                h, w = scaled.shape[:2]
                best_loc = (max_loc[0] + w // 2, max_loc[1] + h // 2, scale)
        return best_loc


class ImagePreprocessor:
    @staticmethod
    def binarize(image: np.ndarray, block_size: int = 11, c: int = 2) -> np.ndarray:
        gray = _to_grayscale(image)
        return cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block_size, c
        )

    @staticmethod
    def clean_noise(image: np.ndarray, kernel_size: int = 2) -> np.ndarray:
        """Morphological opening (erosion + dilation) to remove small noise artifacts."""
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
        return cv2.morphologyEx(image, cv2.MORPH_OPEN, kernel)

    @staticmethod
    def detect_edges(image: np.ndarray, low: int = 50, high: int = 150) -> np.ndarray:
        gray = _to_grayscale(image)
        return cv2.Canny(gray, low, high)

    @staticmethod
    def upscale(image: np.ndarray, factor: int = 3) -> np.ndarray:
        return cv2.resize(image, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)

    @staticmethod
    def preprocess_for_ocr(image: np.ndarray, upscale_factor: int = 3, clean_kernel: int = 2, binarize: bool = False) -> np.ndarray:
        """Preprocessing pipeline for timer OCR: upscale -> (optional binarize) -> clean noise."""
        upscaled = ImagePreprocessor.upscale(image, factor=upscale_factor)
        if binarize:
            upscaled = ImagePreprocessor.binarize(upscaled)
        cleaned = ImagePreprocessor.clean_noise(upscaled, kernel_size=clean_kernel)
        return cleaned
