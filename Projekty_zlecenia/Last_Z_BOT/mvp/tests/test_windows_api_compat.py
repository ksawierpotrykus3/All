"""Tests for Windows API compatibility module.

Validates that version detection and compatibility checks work on all Windows versions.
"""

import unittest
from unittest.mock import patch

from mvp.lib.windows_api_compat import (
    get_windows_version,
    is_windows_7_or_later,
    is_windows_10_or_later,
)


class TestWindowsVersionDetection(unittest.TestCase):
    """Test Windows version detection functionality."""

    @patch("mvp.lib.windows_api_compat.platform.version")
    def test_get_windows_version_windows7(self, mock_version):
        """Test version detection for Windows 7 SP1."""
        mock_version.return_value = "6.1.7601"
        major, minor, build = get_windows_version()
        self.assertEqual(major, 6)
        self.assertEqual(minor, 1)
        self.assertEqual(build, 7601)

    @patch("mvp.lib.windows_api_compat.platform.version")
    def test_get_windows_version_windows10(self, mock_version):
        """Test version detection for Windows 10."""
        mock_version.return_value = "10.0.19045"
        major, minor, build = get_windows_version()
        self.assertEqual(major, 10)
        self.assertEqual(minor, 0)
        self.assertEqual(build, 19045)

    @patch("mvp.lib.windows_api_compat.platform.version")
    def test_get_windows_version_windows11(self, mock_version):
        """Test version detection for Windows 11 (shows as 10.0.x internally)."""
        mock_version.return_value = "10.0.22631"
        major, minor, build = get_windows_version()
        self.assertEqual(major, 10)
        self.assertEqual(minor, 0)
        self.assertEqual(build, 22631)

    @patch("mvp.lib.windows_api_compat.platform.version")
    def test_get_windows_version_partial(self, mock_version):
        """Test version detection with incomplete version string."""
        mock_version.return_value = "10.0"
        major, minor, build = get_windows_version()
        self.assertEqual(major, 10)
        self.assertEqual(minor, 0)
        self.assertEqual(build, 0)

    @patch("mvp.lib.windows_api_compat.platform.version")
    def test_get_windows_version_empty(self, mock_version):
        """Test version detection with empty version string."""
        mock_version.return_value = ""
        major, minor, build = get_windows_version()
        self.assertEqual(major, 0)
        self.assertEqual(minor, 0)
        self.assertEqual(build, 0)

    @patch("mvp.lib.windows_api_compat.platform.version")
    def test_is_windows_7_or_later_windows7(self, mock_version):
        """Test Windows 7 or later check on Windows 7."""
        mock_version.return_value = "6.1.7601"
        self.assertTrue(is_windows_7_or_later())

    @patch("mvp.lib.windows_api_compat.platform.version")
    def test_is_windows_7_or_later_windows10(self, mock_version):
        """Test Windows 7 or later check on Windows 10."""
        mock_version.return_value = "10.0.19045"
        self.assertTrue(is_windows_7_or_later())

    @patch("mvp.lib.windows_api_compat.platform.version")
    def test_is_windows_10_or_later_windows7(self, mock_version):
        """Test Windows 10 or later check on Windows 7 (should be False)."""
        mock_version.return_value = "6.1.7601"
        self.assertFalse(is_windows_10_or_later())

    @patch("mvp.lib.windows_api_compat.platform.version")
    def test_is_windows_10_or_later_windows10(self, mock_version):
        """Test Windows 10 or later check on Windows 10."""
        mock_version.return_value = "10.0.19045"
        self.assertTrue(is_windows_10_or_later())

    @patch("mvp.lib.windows_api_compat.platform.version")
    def test_is_windows_10_or_later_windows11(self, mock_version):
        """Test Windows 10 or later check on Windows 11."""
        mock_version.return_value = "10.0.22631"
        self.assertTrue(is_windows_10_or_later())


class TestWindowsCompatibilityBasic(unittest.TestCase):
    """Basic compatibility tests that should always pass."""

    def test_functions_are_callable(self):
        """Test that all compatibility functions are callable."""
        self.assertTrue(callable(get_windows_version))
        self.assertTrue(callable(is_windows_7_or_later))
        self.assertTrue(callable(is_windows_10_or_later))

    def test_get_windows_version_returns_tuple(self):
        """Test that get_windows_version returns a 3-tuple."""
        result = get_windows_version()
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 3)
        self.assertIsInstance(result[0], int)
        self.assertIsInstance(result[1], int)
        self.assertIsInstance(result[2], int)

    def test_is_windows_7_or_later_always_true(self):
        """Test that is_windows_7_or_later is always True (we support 7+)."""
        self.assertTrue(is_windows_7_or_later())

    def test_is_windows_10_or_later_is_boolean(self):
        """Test that is_windows_10_or_later returns a boolean."""
        result = is_windows_10_or_later()
        self.assertIsInstance(result, bool)


if __name__ == "__main__":
    unittest.main()
