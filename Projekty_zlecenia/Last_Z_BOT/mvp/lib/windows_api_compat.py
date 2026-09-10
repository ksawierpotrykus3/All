"""Windows API compatibility layer for Windows 7 SP1+ support.

Provides version detection and fallback functions for platform-specific features.
"""

import platform
from typing import Tuple


def get_windows_version() -> Tuple[int, int, int]:
    """Return (major, minor, build) tuple from platform.version().

    Examples:
    - Windows 7 SP1: (6, 1, 7601)
    - Windows 10: (10, 0, 19045)
    - Windows 11: (10, 0, 22631)  # Version actually 11 in registry, but platform.version() shows 10.0

    Returns:
        Tuple[int, int, int]: (major, minor, build) version numbers, with 0 as fallback for missing parts
    """
    version = platform.version()
    parts = version.split('.')
    
    def safe_int(s: str) -> int:
        """Safely convert string to int, return 0 on error."""
        try:
            return int(s) if s else 0
        except ValueError:
            return 0
    
    major = safe_int(parts[0]) if len(parts) > 0 else 0
    minor = safe_int(parts[1]) if len(parts) > 1 else 0
    build = safe_int(parts[2]) if len(parts) > 2 else 0
    return (major, minor, build)


def is_windows_7_or_later() -> bool:
    """Check if running on Windows 7 or later.

    Returns:
        bool: True if Windows version is 6.1 (Win7) or higher
    """
    major, _, _ = get_windows_version()
    return major >= 6


def is_windows_10_or_later() -> bool:
    """Check if running on Windows 10 or later.

    Returns:
        bool: True if Windows version is 10.0 (Win10) or higher
    """
    major, _, _ = get_windows_version()
    return major >= 10
