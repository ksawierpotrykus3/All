# mvp/simulator/ui/theme_manager.py
"""
Theme Management System for UI.

Supports dark mode, light mode, and custom color schemes.
Enables real-time theme switching without restart.
"""

import logging
from typing import Dict, Any, Optional
from threading import Lock


logger = logging.getLogger(__name__)


THEMES = {
    'dark': {
        'bg': '#1e1e1e',
        'fg': '#ffffff',
        'accent': '#00ff00',
        'error': '#ff0000',
        'warning': '#ffaa00',
        'canvas_bg': '#0a0a0a',
        'panel_bg': '#252525',
        'border': '#404040',
    },
    'light': {
        'bg': '#ffffff',
        'fg': '#000000',
        'accent': '#0066cc',
        'error': '#cc0000',
        'warning': '#ff8800',
        'canvas_bg': '#f5f5f5',
        'panel_bg': '#eeeeee',
        'border': '#cccccc',
    },
}


class ThemeManager:
    """Manages UI themes with real-time switching capability."""

    def __init__(self, theme_name: str = 'dark'):
        """
        Initialize ThemeManager.

        Args:
            theme_name: Initial theme ('dark' or 'light')
        """
        self._lock = Lock()
        self.current_theme = theme_name if theme_name in THEMES else 'dark'
        self.custom_themes: Dict[str, Dict[str, str]] = {}

        logger.info(f"ThemeManager initialized with theme: {self.current_theme}")

    def get_color(self, color_key: str) -> str:
        """
        Get hex color for key.

        Args:
            color_key: Color key (e.g., 'bg', 'fg', 'accent')

        Returns:
            Hex color string
        """
        with self._lock:
            theme = THEMES.get(self.current_theme, THEMES['dark'])
            return theme.get(color_key, '#ffffff')

    def apply_theme(self, root_widget: Any = None) -> None:
        """
        Apply theme to widget tree.

        Args:
            root_widget: Tkinter root widget (optional)
        """
        if root_widget is None:
            return

        try:
            with self._lock:
                theme = THEMES.get(self.current_theme, THEMES['dark'])

            # Configure root
            root_widget.configure(bg=theme['bg'])

            logger.info(f"Theme applied: {self.current_theme}")

        except Exception as e:
            logger.error(f"Error applying theme: {e}")

    def switch_theme(self, theme_name: str) -> bool:
        """
        Switch theme at runtime.

        Args:
            theme_name: Theme name to switch to

        Returns:
            True if successful
        """
        if theme_name not in THEMES and theme_name not in self.custom_themes:
            logger.warning(f"Theme not found: {theme_name}")
            return False

        try:
            with self._lock:
                self.current_theme = theme_name

            logger.info(f"Theme switched to: {theme_name}")
            return True

        except Exception as e:
            logger.error(f"Error switching theme: {e}")
            return False

    def create_custom_theme(
        self,
        theme_name: str,
        colors: Dict[str, str]
    ) -> bool:
        """
        Create custom theme.

        Args:
            theme_name: Name for custom theme
            colors: Dict of color_key -> hex_color

        Returns:
            True if successful
        """
        try:
            with self._lock:
                self.custom_themes[theme_name] = colors

            logger.info(f"Custom theme created: {theme_name}")
            return True

        except Exception as e:
            logger.error(f"Error creating custom theme: {e}")
            return False

    def get_theme_colors(self) -> Dict[str, str]:
        """
        Get all colors for current theme.

        Returns:
            Dict of color_key -> hex_color
        """
        with self._lock:
            if self.current_theme in THEMES:
                return dict(THEMES[self.current_theme])
            else:
                return dict(self.custom_themes.get(self.current_theme, THEMES['dark']))

    def list_themes(self) -> list:
        """
        List available themes.

        Returns:
            List of theme names
        """
        with self._lock:
            return list(THEMES.keys()) + list(self.custom_themes.keys())

    def validate_contrast(self, fg_color: str, bg_color: str) -> bool:
        """
        Validate color contrast (WCAG AA standard).

        Args:
            fg_color: Foreground color (hex)
            bg_color: Background color (hex)

        Returns:
            True if contrast is sufficient
        """
        try:
            # Simple contrast check: convert to RGB and calculate luminance
            # WCAG AA requires contrast ratio of 4.5:1 for normal text

            def hex_to_rgb(hex_color: str) -> tuple:
                hex_color = hex_color.lstrip('#')
                return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

            def get_luminance(rgb: tuple) -> float:
                r, g, b = [x / 255.0 for x in rgb]
                r = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
                g = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
                b = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
                return 0.2126 * r + 0.7152 * g + 0.0722 * b

            fg_rgb = hex_to_rgb(fg_color)
            bg_rgb = hex_to_rgb(bg_color)

            fg_lum = get_luminance(fg_rgb)
            bg_lum = get_luminance(bg_rgb)

            lighter = max(fg_lum, bg_lum)
            darker = min(fg_lum, bg_lum)

            contrast_ratio = (lighter + 0.05) / (darker + 0.05)

            return contrast_ratio >= 4.5

        except Exception as e:
            logger.error(f"Error validating contrast: {e}")
            return True
