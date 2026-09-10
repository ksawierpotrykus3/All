import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import Canvas

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageTk

from mvp import macro_def as md
from mvp.bot.coordinates import GameROI, WindowContext
from mvp.simulator.variants import VariantExecutor

# Deterministic state -> displayed image key mapping.
# The bot loop is: no_chat -> chat (open chat bar) -> alert (alliance tab shows
# helicopter alert) -> helka (clicked the alert). After WATCH_TIMER the bridge
# resets back to no_chat for the next iteration.
#
# NOTE: "alert" is special — 1_heli_alert_appearing_in_chat.png is only a small
# 303x105 snippet, so the full "alert appears in chat" frame is composed by
# overlaying that snippet onto the chat screen (see _compose_alert_frame).
_STATE_IMAGE = {
    "no_chat": "no_chat",
    "chat": "chat",
    "alert": "chat",  # base; the alert snippet is overlaid on top
    "helka": "helka",
}

# ROIs visualized on every frame. The active (clickable) one is highlighted.
_MACRO_ROIS = [
    ("scroll_listen", md._ROI_SCROLL_LISTEN),
    ("chat_bar", md._ROI_CHAT_BAR),
    ("alliance_tab", md._ROI_ALLIANCE_TAB),
    ("heli_select", md._ROI_HELICOPTER_SELECT),
    ("explore", md._ROI_EXPLORE),
    ("post_explore", md._ROI_POST_EXPLORE),
    ("timer", md._ROI_TIMER),
    ("camera_zoom", md._ROI_CAMERA_ZOOM),
    ("chat_arrow", md._ROI_CHAT_ARROW),
]

# The ROI whose click drives the transition out of each state. In "alert" the
# interactive user may click anywhere in the scroll ROI; bot mode additionally
# requires the click to land near the OCR-detected alert point (strict mode).
_ACTIVE_ROI_BY_STATE = {
    "no_chat": md._ROI_CHAT_BAR,
    "chat": md._ROI_ALLIANCE_TAB,
    "alert": md._ROI_SCROLL_LISTEN,
    "helka": None,  # macro continues clicking inside helka; no state change
}


def _roi_to_pixels(roi_pct: dict, frame_w: int, frame_h: int) -> tuple[int, int, int, int]:
    """Convert a macro_def ROI dict to frame pixel rect.

    Uses the exact same conversion the macro engine uses (roi_to_frame_pixels),
    so simulator click targets line up with the bot's OCR/click coordinates.
    """
    roi = GameROI(
        left=roi_pct.get("left", 0),
        top=roi_pct.get("top", 0),
        right=roi_pct.get("right", 100),
        bottom=roi_pct.get("bottom", 100),
        anchor=roi_pct.get("anchor", "stretch"),
    )
    ctx = WindowContext(left=0, top=0, width=frame_w, height=frame_h)
    return ctx.roi_to_frame_pixels(roi, frame_w, frame_h)


class GameSimulator:
    """Deterministic state-machine simulator driven by the bot's real clicks.

    The bot reads frames via get_current_frame_raw() (sized 1:1 to the window
    client area) and clicks via SendInput into the Tkinter window. Each click is
    mapped back to frame coordinates and advances the state machine only when it
    lands in the correct ROI for the current state.
    """

    def __init__(self, data_dir: str | Path | None = None, metrics=None):
        self.metrics = metrics
        if data_dir is None:
            repo_root = Path(__file__).resolve().parents[2]
            candidates = [
                repo_root / "data" / "macro_testing",
                Path.cwd() / "data" / "macro_testing",
            ]
            for candidate in candidates:
                if candidate.is_dir():
                    data_dir = candidate
                    break
            else:
                data_dir = repo_root / "data" / "macro_testing"

        img_dir = Path(data_dir)
        raw_image_map = {
            "chat": img_dir / "1_scan_chat_without_arrow.png",
            "helka": img_dir / "helka_scrolled.png",
            "alert": img_dir / "1_heli_alert_appearing_in_chat.png",
            "no_chat": img_dir / "no_chat.png",
            "chat_arrow": img_dir / "1_scan_chat_with_arrow.png",
            "details": img_dir / "details.png",
        }

        # Full-screen assets have slightly different native sizes (1923x1075,
        # 1918x1020, 1920x1080, ...). Normalise them all to the canonical game
        # viewport (1920x1080) so every state renders with the same aspect and
        # the percentage-based ROIs do not jump between states. The "alert" image
        # is a small 303x105 snippet and is intentionally NOT normalised.
        _CANONICAL_W, _CANONICAL_H = 1920, 1080

        self.images = {}
        for name, img_path in raw_image_map.items():
            img = cv2.imread(str(img_path)) if img_path.is_file() else None
            if img is None:
                print(f"WARNING: {name} ({img_path}) not loaded, creating fallback placeholder")
                if name == "alert":
                    img = np.zeros((105, 303, 3), dtype=np.uint8)
                    img[:] = (20, 120, 200)
                    cv2.putText(
                        img,
                        "ALERT",
                        (20, 60),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1.0,
                        (255, 255, 255),
                        2,
                    )
                else:
                    img = np.zeros((_CANONICAL_H, _CANONICAL_W, 3), dtype=np.uint8)
                    cv2.putText(
                        img,
                        name.upper(),
                        (50, 100),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1.5,
                        (0, 255, 0),
                        2,
                    )
            if name != "alert":
                h, w = img.shape[:2]
                if (w, h) != (_CANONICAL_W, _CANONICAL_H):
                    img = cv2.resize(
                        img, (_CANONICAL_W, _CANONICAL_H), interpolation=cv2.INTER_AREA
                    )
            self.images[name] = img
            h, w = img.shape[:2]
            print(f"Loaded {name}: {w}x{h}")

        self._lock = threading.Lock()
        self.current_state = "no_chat"
        self.viewport_size: tuple[int, int] = (1920, 1080)

        self.clicks_received = 0
        self.click_log: list[dict] = []
        self.click_markers: list[tuple[int, int, str, bool | None]] = []
        self.click_accuracy_percent = 0.0

        self.expected_chat_click_pct: tuple[float, float] | None = None
        self.chat_click_tolerance_pct: float = 5.0
        # In bot mode the alert click must land on the OCR-detected position.
        # In interactive mode any click inside the scroll ROI counts.
        self.strict_alert_hit = False
        # Timestamp when the chat->alert transition fired; used by BotBridge to
        # compute the OCR->click detection latency.
        self.alert_start_time: float | None = None

        # Timer overlay state (kept for the WATCH_TIMER visualisation).
        self.timer_seconds = 300
        self.timer_start = time.time()

        self.running = True

        # Bot frame source wiring (frame_queue kept for API compatibility).
        self.frame_queue = None
        self.bot_thread = None
        self.latest_rois: list[dict] = []
        self._stop_frame_reader = threading.Event()

        self.variant_executor = VariantExecutor(session_id=None)
        self.current_variant = None

    def apply_variant(self, preset_name: str) -> None:
        self.variant_executor.apply_preset(preset_name)
        self.current_variant = self.variant_executor.current_variant

    def set_viewport_size(self, width: int, height: int) -> None:
        if width > 1 and height > 1:
            with self._lock:
                self.viewport_size = (int(width), int(height))

    def _state_image(self) -> np.ndarray:
        with self._lock:
            key = _STATE_IMAGE.get(self.current_state, "no_chat")
        return self.images[key]

    def _compose_alert_frame(self, base: np.ndarray) -> np.ndarray:
        """Overlay the helicopter alert snippet onto the chat frame.

        The macro's SCROLL_LISTEN_CHAT scans the scroll_listen ROI; the alert
        must appear inside that ROI so find_helicopter_alert() can detect it.
        """
        alert_img = self.images.get("alert")
        if alert_img is None:
            return base
        fh, fw = base.shape[:2]
        ah, aw = alert_img.shape[:2]
        # Scale the snippet to a readable height relative to the scroll ROI.
        scale = fh / 1080.0
        ah_s = max(1, int(ah * scale))
        aw_s = max(1, int(aw * scale))
        if (aw_s, ah_s) != (aw, ah):
            alert_img = cv2.resize(alert_img, (aw_s, ah_s), interpolation=cv2.INTER_AREA)
            ah, aw = ah_s, aw_s
        # Place inside the scroll_listen ROI, centered horizontally.
        roi_l, roi_t, roi_r, roi_b = _roi_to_pixels(md._ROI_SCROLL_LISTEN, fw, fh)
        x = roi_l + (roi_r - roi_l - aw) // 2
        y = roi_t + int((roi_b - roi_t - ah) * 0.5)
        x = max(0, min(fw - aw, x))
        y = max(0, min(fh - ah, y))
        base[y : y + ah, x : x + aw] = cv2.addWeighted(
            alert_img, 0.9, base[y : y + ah, x : x + aw], 0.1, 0
        )
        return base

    def get_current_frame_raw(self) -> np.ndarray:
        """Frame the bot sees: current state image scaled to fit the viewport.

        Uses `contain` scaling: the whole image is scaled down to fit inside the
        viewport while preserving the aspect ratio, then centered with padding.
        The entire game view (including its full height) is always visible, so
        nothing is ever cut off by a maximized window / taskbar.
        """
        with self._lock:
            state = self.current_state
            vw, vh = self.viewport_size
        img = self._state_image()
        h, w = img.shape[:2]

        # Scale to fit inside the viewport (contain: preserve aspect, no crop).
        scale = min(vw / w, vh / h)
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
        if (new_w, new_h) != (w, h):
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

        # Center the (smaller-or-equal) image and letterbox the remainder.
        cropped = np.zeros((vh, vw, 3), dtype=np.uint8)
        off_x = max(0, (vw - new_w) // 2)
        off_y = max(0, (vh - new_h) // 2)
        cropped[off_y : off_y + new_h, off_x : off_x + new_w] = img
        # Compose the alert on the (viewport-sized) cropped frame so the alert
        # center lands in viewport coordinates and matches Tkinter click coords.
        if state == "alert":
            cropped = self._compose_alert_frame(cropped)
        return cropped

    def get_current_frame_cropped(self, viewport_width: int, viewport_height: int) -> np.ndarray:
        # Kept for API compatibility: the raw frame is already viewport-sized.
        return self.get_current_frame_raw()

    def _in_roi(self, roi_pct: dict, fx: float, fy: float) -> bool:
        # The rendered frame is always exactly viewport-sized, so the ROI test
        # can use the cached viewport size instead of rebuilding a frame.
        with self._lock:
            fw, fh = self.viewport_size
        left, top, right, bottom = _roi_to_pixels(roi_pct, fw, fh)
        return left <= fx <= right and top <= fy <= bottom

    def _hit_expected_alert(self, fx: float, fy: float) -> bool:
        with self._lock:
            fw, fh = self.viewport_size
        if self.strict_alert_hit:
            # Bot mode: the alert transition must be driven by the bot's Step-2
            # click on the OCR-detected alert position. Until that position is
            # known (set on SCROLL_LISTEN_CHAT success), no click counts.
            if self.expected_chat_click_pct is None:
                return False
            ex, ey = self.expected_chat_click_pct
            px = ex / 100.0 * fw
            py = ey / 100.0 * fh
            tol = self.chat_click_tolerance_pct / 100.0 * fw
            return abs(fx - px) <= tol and abs(fy - py) <= tol
        # Interactive mode: any click inside the scroll ROI dismisses the alert.
        return self._in_roi(md._ROI_SCROLL_LISTEN, fx, fy)

    def handle_click(self, fx: float, fy: float) -> bool:
        """Advance the state machine if the click lands in the correct ROI."""
        with self._lock:
            state = self.current_state

        hit: bool | None = False
        next_state: str | None = None
        if state == "no_chat":
            hit = self._in_roi(md._ROI_CHAT_BAR, fx, fy)
            if hit:
                next_state = "chat"
        elif state == "chat":
            hit = self._in_roi(md._ROI_ALLIANCE_TAB, fx, fy)
            if hit:
                next_state = "alert"
        elif state == "alert":
            hit = self._hit_expected_alert(fx, fy)
            if hit:
                next_state = "helka"
        elif state == "helka":
            # The macro keeps clicking in helka (select/explore/zoom/spam); those
            # are legitimate actions that do not advance the state machine. They
            # are logged as neutral so they do not distort click accuracy.
            hit = None

        with self._lock:
            self.clicks_received += 1
            if next_state is not None:
                self.current_state = next_state
                if next_state == "alert":
                    # Marks the moment the alert became visible; BotBridge reads
                    # it to report the OCR->click detection latency.
                    self.alert_start_time = time.time()

        self._log_click(fx, fy, hit, state)
        if hit:
            print(f"[HIT] click @({fx:.0f},{fy:.0f}) in '{state}' -> '{self.current_state}'")
        elif hit is None:
            print(f"[LOG] click @({fx:.0f},{fy:.0f}) in '{state}' (in-helka action, neutral)")
        else:
            print(f"[MISS] click @({fx:.0f},{fy:.0f}) in '{state}' (no transition)")
        return bool(hit)

    def _log_click(self, fx: float, fy: float, hit: bool | None, state: str) -> None:
        entry = {
            "timestamp": time.time(),
            "x": int(fx),
            "y": int(fy),
            "hit": hit,
            "roi_name": state,
            "state": state,
        }
        self.click_log.append(entry)
        self.click_markers.append((int(fx), int(fy), state, hit))
        # Only real hit attempts count toward accuracy; neutral (in-helka)
        # clicks and marker-only entries are excluded.
        attempts = [e for e in self.click_log if e["hit"] is not None]
        if attempts:
            hits = sum(1 for e in attempts if e["hit"])
            self.click_accuracy_percent = hits / len(attempts) * 100
        # NOTE: metrics are recorded exclusively by BotBridge (bot mode) on
        # SCROLL/WATCH success. Recording here per-click used the same
        # `iterations` keys as the bridge and corrupted the exports.

    def reset_to_chat(self) -> None:
        with self._lock:
            self.current_state = "no_chat"
            self.alert_start_time = None
        self.expected_chat_click_pct = None
        print("[STATE] reset to 'no_chat' for next macro iteration")

    def get_click_statistics(self) -> dict:
        attempts = [e for e in self.click_log if e["hit"] is not None]
        hits = sum(1 for e in attempts if e["hit"])
        return {
            "total_clicks": len(self.click_log),
            "accuracy_percent": self.click_accuracy_percent,
            "hits": hits,
        }

    def connect_to_bot(self, bot_runner) -> None:
        if hasattr(bot_runner, "capture") and bot_runner.capture is not None:
            bot_runner.capture.set_frame_source(self.get_current_frame_raw)
        self.frame_queue = getattr(bot_runner, "frame_queue", None)
        print("[SIMULATOR] connected to bot (simulator now feeds bot frames)")

    def start_frame_reader(self) -> None:
        pass

    def stop_frame_reader(self) -> None:
        pass

    def render_timer_on_frame(self, frame: np.ndarray) -> np.ndarray:
        elapsed = time.time() - self.timer_start
        seconds_left = max(0, self.timer_seconds - int(elapsed))
        mins = seconds_left // 60
        secs = seconds_left % 60
        timer_text = f"{mins}:{secs:02d}"
        cv2.putText(
            frame,
            timer_text,
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.2,
            (0, 255, 0),
            2,
        )
        return frame

    def render_roi_boxes(self, frame: np.ndarray) -> np.ndarray:
        fh, fw = frame.shape[:2]
        with self._lock:
            state = self.current_state
        active_roi = _ACTIVE_ROI_BY_STATE.get(state)

        # Translucent highlight over the active click target so the interactive
        # user can always see where the next click has to land.
        highlight = frame.copy()
        for _name, roi_pct in _MACRO_ROIS:
            if roi_pct is not active_roi:
                continue
            left, top, right, bottom = _roi_to_pixels(roi_pct, fw, fh)
            cv2.rectangle(highlight, (left, top), (right, bottom), (0, 255, 0), -1)
        frame = cv2.addWeighted(highlight, 0.28, frame, 0.72, 0)

        for name, roi_pct in _MACRO_ROIS:
            left, top, right, bottom = _roi_to_pixels(roi_pct, fw, fh)
            if roi_pct is active_roi:
                color = (0, 255, 0)  # green = active click target
                thickness = 3
            else:
                color = (180, 180, 180)  # gray = informational
                thickness = 1
            cv2.rectangle(frame, (left, top), (right, bottom), color, thickness)
            cv2.putText(
                frame,
                name,
                (left, max(16, top - 5)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2,
                cv2.LINE_AA,
            )

        # Click markers: green dot for hit, red dot for miss, yellow for
        # neutral (in-helka) macro actions.
        for mx, my, _st, hit in self.click_markers:
            if hit is None:
                color = (0, 255, 255)
            elif hit:
                color = (0, 255, 0)
            else:
                color = (0, 0, 255)
            cv2.circle(frame, (mx, my), 6, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.circle(frame, (mx, my), 5, color, -1, cv2.LINE_AA)

        # In bot mode (strict) during the alert state, draw the exact point the
        # macro must click: the OCR-detected alert position from the last scan.
        if state == "alert" and self.strict_alert_hit and self.expected_chat_click_pct:
            ex, ey = self.expected_chat_click_pct
            px = int(ex / 100.0 * fw)
            py = int(ey / 100.0 * fh)
            cv2.line(frame, (px - 12, py), (px + 12, py), (0, 165, 255), 2, cv2.LINE_AA)
            cv2.line(frame, (px, py - 12), (px, py + 12), (0, 165, 255), 2, cv2.LINE_AA)
            cv2.circle(frame, (px, py), 8, (0, 165, 255), 2, cv2.LINE_AA)

        return frame


class SimulatorUI:
    def __init__(self, sim=None, on_start=None, on_stop=None):
        self.sim = sim if sim is not None else GameSimulator()
        self.root = None
        self.canvas = None
        self.running = True
        self.on_start = on_start
        self.on_stop = on_stop

    def _active_target_label(self, state: str) -> str:
        if state == "no_chat":
            return "KLIKNIJ W ZIELONY OBWOD (dolny pasek czatu) -> otworzysz czat"
        if state == "chat":
            return "KLIKNIJ W ZIELONY OBWOD (zakladka sojuszu u gory) -> pojawi sie alert"
        if state == "alert":
            return "KLIKNIJ W ZIELONY OBWOD / alert (srodek ekranu) -> przejdziesz do helikoptera"
        if state == "helka":
            return "Widok helikoptera - kliknięcia neutralne.  R = restart pętli | Q = wyjście"
        return ""

    @staticmethod
    def _fit_geometry(root: tk.Tk) -> None:
        """Pick the largest 16:9 client size that fits on the work area.

        The game assets are 16:9, so a 16:9 window means the rendered frame and
        the ROIs map 1:1 to the real-game geometry (no letterbox drift).
        """
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        h = int(sh * 0.92)  # leave room for the taskbar / window title
        w = int(h * 16 / 9)
        if w > sw:
            w = sw
            h = int(w * 9 / 16)
        root.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 2 - 15)}")
        root.minsize(640, 360)
        root.resizable(False, False)

    def run(self):
        root = tk.Tk()
        root.title("LastZ Simulator (16:9)")
        self._fit_geometry(root)

        canvas = Canvas(root, bg="black")
        canvas.pack(fill="both", expand=True)

        # Start the bot only after the window exists and has its final size, so
        # the window finder / frame geometry are correct from the first frame.
        if self.on_start is not None:
            root.after(250, self.on_start)

        photo_image = None
        last_size = {"w": 0, "h": 0}
        last_sig: tuple | None = None

        def shutdown():
            if not self.sim.running:
                return
            self.sim.running = False
            if self.on_stop is not None:
                self.on_stop()
            root.destroy()

        def render_and_display():
            nonlocal photo_image, last_size, last_sig

            if not self.sim.running:
                root.quit()
                return

            c_width = canvas.winfo_width()
            c_height = canvas.winfo_height()
            if c_width <= 1 or c_height <= 1:
                c_width = 1920
                c_height = 1080

            if c_width != last_size["w"] or c_height != last_size["h"]:
                print(f"[RESIZE] Canvas: {c_width}x{c_height}")
                last_size = {"w": c_width, "h": c_height}

            self.sim.set_viewport_size(c_width, c_height)
            with self.sim._lock:
                state = self.sim.current_state

            # Dirty check: skip the expensive render pipeline (resize + compose
            # + PIL + canvas redraw) when nothing visible changed. The timer
            # ticks once per second in helka, so include its displayed value.
            sig: tuple = (state, c_width, c_height, len(self.sim.click_markers))
            if state == "helka":
                sig += (int(time.time() - self.sim.timer_start),)
            if state == "alert" and self.sim.strict_alert_hit:
                # The orange crosshair target changes when the bridge reports a
                # fresh OCR position; include it so the frame refreshes.
                sig += (self.sim.expected_chat_click_pct,)
            if sig == last_sig:
                root.after(16, render_and_display)
                return

            frame_bgr = self.sim.get_current_frame_raw()
            frame_bgr = self.sim.render_roi_boxes(frame_bgr)
            if state == "helka":
                frame_bgr = self.sim.render_timer_on_frame(frame_bgr)

            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(frame_rgb)

            draw = ImageDraw.Draw(pil_img)
            draw.text((10, 10), f"State: {state}", fill=(0, 255, 0))
            draw.text((10, 40), f"Clicks: {self.sim.clicks_received}", fill=(255, 255, 255))
            stats = self.sim.get_click_statistics()
            draw.text(
                (10, 70),
                f"Accuracy: {stats['accuracy_percent']:.1f}% ({stats['hits']}/{stats['total_clicks']})",
                fill=(100, 255, 100),
            )
            hint = self._active_target_label(state)
            if hint:
                draw.text((10, 100), hint, fill=(0, 255, 255))

            photo_image = ImageTk.PhotoImage(pil_img)
            canvas.delete("all")
            canvas.create_image(0, 0, image=photo_image, anchor="nw")
            last_sig = sig
            root.after(16, render_and_display)

        def on_key(event):
            key = event.keysym.lower()
            if key == "q":
                shutdown()
            elif key == "r":
                self.sim.reset_to_chat()

        def on_click(event):
            self.sim.handle_click(event.x, event.y)

        root.protocol("WM_DELETE_WINDOW", shutdown)
        root.bind("<Key>", on_key)
        root.bind("<Button-1>", on_click)

        root.after(16, render_and_display)
        try:
            root.mainloop()
        except KeyboardInterrupt:
            shutdown()


if __name__ == "__main__":
    print("Starting deterministic simulator")
    ui = SimulatorUI()
    ui.run()