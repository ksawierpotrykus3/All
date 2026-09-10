"""Moduł wizji komputerowej do detekcji okien potwierdzenia (np. Tips/Confirm).

W grze Last Z przy marszu wojsk >20 minut pojawia się modalne okienko 'Tips'
z żółtym przyciskiem 'Confirm' oraz polem 'Don't remind me again'.
Detekcja opiera się na barwie i geometrii przycisku, dzięki czemu działa
w 100% niezależnie od języka gry.
"""

from __future__ import annotations

import cv2
import numpy as np


def find_march_confirm_modal(
    frame: np.ndarray | None,
    roi_box: tuple[float, float, float, float] = (0.28, 0.42, 0.62, 0.72),
) -> tuple[int, int, int, int] | None:
    """Wykrywa żółty przycisk Confirm okna potwierdzenia długiego marszu ('Tips').

    Przeszukuje szeroki obszar środka ekranu (domyślnie X: 28%-62%, Y: 42%-72%).
    Zwraca krotkę (confirm_x, confirm_y, checkbox_x, checkbox_y) w pikselach klatki,
    lub None, jeśli okienko nie występuje na ekranie.
    """
    if frame is None or frame.size == 0 or len(frame.shape) < 3 or frame.shape[2] < 3:
        return None

    h, w = frame.shape[:2]
    x1 = max(0, int(w * roi_box[0]))
    y1 = max(0, int(h * roi_box[1]))
    x2 = min(w, int(w * roi_box[2]))
    y2 = min(h, int(h * roi_box[3]))

    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return None

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

    # Żółto-złoty przycisk Confirm w grze: Hue 15-35, Saturation 120-255, Value 120-255
    lower_yellow = np.array([15, 120, 120], dtype=np.uint8)
    upper_yellow = np.array([35, 255, 255], dtype=np.uint8)
    mask = cv2.inRange(hsv, lower_yellow, upper_yellow)

    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates: list[tuple[int, float, float, int, int]] = []

    for c in cnts:
        bx, by, bw, bh = cv2.boundingRect(c)
        # Przycisk ma charakterystyczne proporcje (prostokąt o aspect ratio 1.8 - 5.0)
        # oraz minimalne wymiary:
        if bw > 35 and bh > 10 and 1.8 <= (bw / bh) <= 5.0:
            cx = x1 + bx + bw / 2.0
            cy = y1 + by + bh / 2.0
            area = bw * bh
            candidates.append((area, cx, cy, bw, bh))

    if not candidates:
        return None

    # Największy żółty prostokąt to właściwy przycisk Confirm
    candidates.sort(key=lambda item: item[0], reverse=True)
    _, confirm_x, confirm_y, bw, bh = candidates[0]

    # Checkbox 'Don't remind me again' znajduje się dokładnie nad przyciskiem Confirm:
    # przesunięcie w pionie to ok. 1.6 wysokości przycisku w górę
    cb_x = confirm_x + (0.05 * bw)
    cb_y = confirm_y - (1.6 * bh)

    return (
        int(round(confirm_x)),
        int(round(confirm_y)),
        int(round(cb_x)),
        int(round(cb_y)),
    )
