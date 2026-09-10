from __future__ import annotations

import json
import logging
import os
import string
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def parse_key(name: str) -> int:
    name_upper = name.strip().upper()
    if name_upper.startswith("F") and len(name_upper) in (2, 3):
        suffix = name_upper[1:]
        if suffix.isdigit():
            num = int(suffix)
            if 1 <= num <= 12:
                return 0x6F + num
    if len(name_upper) == 1 and name_upper in string.ascii_uppercase:
        return 0x41 + string.ascii_uppercase.index(name_upper)
    raise ValueError(f"Unsupported key name: {name}")


@dataclass
class MVPConfig:

    process_name: str = "Survival.exe"
    scan_fps: int = 30
    click_min_delay_ms: int = 280
    click_max_delay_ms: int = 350
    spam_noise_px: float = 3.0
    spam_clicks_per_sec: int = 30
    spam_threshold_s: int = 5
    spam_duration_s: float = 6.0
    idle_check_interval_s: float = 3.0
    fast_check_interval_s: float = 0.2
    fast_threshold_s: int = 60
    t0_lead_time_s: float = 0.3
    watch_timer_timeout_s: float = 1800.0
    preview_enabled: bool = False
    preview_scale: float = 1.0

    zoom_scroll_ticks: int = 25
    zoom_scroll_interval_s: float = 0.035

    hotkey_spam: str = "F1"
    hotkey_start_stop: str = "F6"
    hotkey_emergency: str = "F8"

    prevent_sleep: bool = True
    prevent_display_off: bool = True
    anti_sleep_away_mode: bool = False

    anti_detect_enabled: bool = True
    anti_detect_check_interval_s: float = 30.0

    notify_enabled: bool = True
    notify_sound_path: str = ""

    chat_arrow_threshold: float = 0.92
    chat_arrow_delay_s: float = 0.35

    details_recovery_enabled: bool = True
    details_dismiss_delay_s: float = 5.0

    hysteresis_confirmations: int = 1

    log_to_file: bool = False
    log_dir: str = "logs"
    log_verbose: bool = True
    debug_macro_log: bool = False

    app_version: str = "0.1.0"

    backend_url: str = ""
    license_key: str = ""

    process_priority: str = "normal"

    max_iterations: int = 0
    max_runtime_s: float = 0.0

    click_jitter_ms: float = 0.5

    def validate(self) -> tuple[bool, list[str]]:
        errors: list[str] = []

        if not self.process_name.strip():
            errors.append("process_name must not be empty")
        if not (1 <= self.scan_fps <= 60):
            errors.append("scan_fps must be between 1 and 60")
        if self.click_min_delay_ms < 0 or self.click_max_delay_ms < 0:
            errors.append("click delays must be >= 0")
        if self.click_max_delay_ms < self.click_min_delay_ms:
            errors.append("click_max_delay_ms must be >= click_min_delay_ms")
        if self.spam_noise_px < 0:
            errors.append("spam_noise_px must be >= 0")
        if self.process_priority not in ("normal", "below_normal", "idle"):
            errors.append(
                f"process_priority must be 'normal', 'below_normal' or 'idle', got {self.process_priority}"
            )
        if self.max_iterations < 0:
            errors.append("max_iterations must be >= 0 (0 = unlimited)")
        if self.max_runtime_s < 0:
            errors.append("max_runtime_s must be >= 0 (0 = unlimited)")
        if not (1 <= self.spam_clicks_per_sec <= 35):
            errors.append(
                "spam_clicks_per_sec must be between 1 and 35 (safe cap in 60 FPS clean game)"
            )
        if not (1 <= self.spam_threshold_s <= 3600):
            errors.append("spam_threshold_s must be between 1 and 3600")
        if not (0.1 <= self.spam_duration_s <= 60):
            errors.append("spam_duration_s must be between 0.1 and 60")
        if not (0.05 <= self.idle_check_interval_s <= 60):
            errors.append("idle_check_interval_s must be between 0.05 and 60")
        if not (0.05 <= self.fast_check_interval_s <= 5):
            errors.append("fast_check_interval_s must be between 0.05 and 5")
        if not (1 <= self.fast_threshold_s <= 3600):
            errors.append("fast_threshold_s must be between 1 and 3600")
        if not (1.0 <= self.watch_timer_timeout_s <= 86400.0):
            errors.append("watch_timer_timeout_s must be between 1.0 and 86400.0")
        if not (0.1 <= self.chat_arrow_threshold <= 1.0):
            errors.append("chat_arrow_threshold must be between 0.1 and 1.0")
        if not (0.0 <= self.details_dismiss_delay_s <= 60.0):
            errors.append("details_dismiss_delay_s must be between 0.0 and 60.0")
        if not (0.1 <= self.preview_scale <= 1.0):
            errors.append("preview_scale must be between 0.1 and 1.0")
        if not (1 <= self.zoom_scroll_ticks <= 100):
            errors.append("zoom_scroll_ticks must be between 1 and 100")
        if not (0.005 <= self.zoom_scroll_interval_s <= 1.0):
            errors.append("zoom_scroll_interval_s must be between 0.005 and 1.0")

        for field_name in ("hotkey_spam", "hotkey_start_stop", "hotkey_emergency"):
            val = str(getattr(self, field_name)).strip()
            if not val:
                errors.append(f"{field_name} must not be empty")
            else:
                try:
                    parse_key(val)
                except ValueError:
                    errors.append(f"{field_name} '{val}' is invalid (supported: F1-F12, A-Z)")

        if not (0.0 <= self.click_jitter_ms <= 50.0):
            errors.append("click_jitter_ms must be between 0.0 and 50.0")
        return (len(errors) == 0, errors)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MVPConfig:
        known = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in known}
        return cls(**kwargs)

    @classmethod
    def default(cls) -> MVPConfig:
        return cls()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def load(cls, path: Path) -> MVPConfig:
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp_path, path)

    @classmethod
    def load_or_default(cls, path: Path) -> MVPConfig:
        if not path.exists():
            cfg = cls.default()
            try:
                cfg.save(path)
            except OSError as exc:
                logger.warning("Could not write default config to %s: %s", path, exc)
            return cfg
        try:
            return cls.load(path)
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.error(
                "Failed to load config from %s (%s) — falling back to defaults",
                path,
                exc,
            )
            cfg = cls.default()
            try:
                cfg.save(path)
            except OSError as save_exc:
                logger.warning("Could not overwrite corrupt config %s: %s", path, save_exc)
            return cfg