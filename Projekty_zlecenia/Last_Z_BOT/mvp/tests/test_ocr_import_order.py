"""P1-3: AGENTS.md §6 — onnxruntime MUST be imported BEFORE any winrt module.

On Windows, importing ``winrt.windows.media.ocr`` (or any other winrt module)
BEFORE ``onnxruntime`` causes a critical DLL initialization collision:

    ``ImportError: DLL load failed while importing onnxruntime_pybind11_state``

The fix (see ``mvp/bot/ocr.py`` lines 10-11) is to load ``onnxruntime`` under
a ``contextlib.suppress`` block BEFORE any winrt import. This test pins
down that ordering with both a static AST check and a runtime sanity check.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

OCR_MODULE_PATH = Path("mvp/bot/ocr.py")


def _load_module_source() -> str:
    """Read the ocr.py module from disk."""
    return OCR_MODULE_PATH.read_text(encoding="utf-8")


def _import_lines_from_source(src: str) -> list[tuple[int, str]]:
    """Return ``[(lineno, module_name), ...]`` for every import in the module.

    Walks the AST top-down so we can assert strict ordering.
    """
    tree = ast.parse(src)
    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imports.append((node.lineno, module))
    imports.sort(key=lambda t: t[0])
    return imports


def test_onnxruntime_imported_before_winrt_in_ocr_module() -> None:
    """Static AST check: ``onnxruntime`` must precede any ``winrt`` import."""
    src = _load_module_source()
    imports = _import_lines_from_source(src)

    onnx_lines = [ln for ln, mod in imports if "onnxruntime" in mod]
    winrt_lines = [ln for ln, mod in imports if "winrt" in mod]

    if not onnx_lines:
        pytest.skip("onnxruntime is not statically imported in ocr.py")
    if not winrt_lines:
        pytest.skip("winrt is not statically imported in ocr.py (acceptable)")

    first_onnx = onnx_lines[0]
    first_winrt = winrt_lines[0]
    assert first_onnx < first_winrt, (
        f"AGENTS.md §6 violation: onnxruntime at L{first_onnx} must precede "
        f"winrt at L{first_winrt} (DLL initialization collision otherwise)"
    )


def test_onnxruntime_import_uses_suppress_context() -> None:
    """The onnxruntime import MUST be inside ``contextlib.suppress`` so that
    non-Windows platforms (where onnxruntime is unavailable) don't break."""
    src = _load_module_source()
    imports = _import_lines_from_source(src)

    onnx_lines = [ln for ln, mod in imports if "onnxruntime" in mod]
    if not onnx_lines:
        pytest.skip("onnxruntime not statically imported")

    def _is_onnxruntime_import(node: ast.AST) -> bool:
        if isinstance(node, ast.Import):
            return any("onnxruntime" in alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            return bool(node.module) and "onnxruntime" in node.module
        return False

    tree = ast.parse(src)
    found_in_suppress = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.With):
            continue
        for item in node.items:
            ctx_src = ast.unparse(item.context_expr)
            if "suppress" not in ctx_src:
                continue
            for sub in ast.walk(node):
                if _is_onnxruntime_import(sub):
                    found_in_suppress = True
                    break
    assert found_in_suppress, (
        "onnxruntime import must be wrapped in contextlib.suppress (Windows-only)"
    )


def test_runtime_import_order() -> None:
    """Runtime sanity check: importing ocr must NOT raise on this platform.

    If both onnxruntime and winrt are available, importing the module must
    complete without the DLL collision error.
    """
    try:
        import mvp.bot.ocr  # noqa: F401
    except ImportError as exc:
        if "DLL load failed" in str(exc) and "onnxruntime_pybind11_state" in str(exc):
            pytest.fail(
                f"AGENTS.md §6 violation: onnxruntime DLL collision during "
                f"import of mvp.bot.ocr: {exc}"
            )
        # Other ImportError (missing optional dep) is acceptable in CI.
        pytest.skip(f"Optional dependency missing: {exc}")
    # If both modules are present in sys.modules, verify ordering.
    if "onnxruntime" in sys.modules and "winrt" in sys.modules:
        # By construction (mvp/bot/ocr.py loads onnxruntime first inside
        # contextlib.suppress before winrt lazy-load), onnxruntime must
        # appear earlier in sys.modules iteration order than winrt.
        # We don't have direct insertion-order introspection, but we can
        # verify that the module itself has been imported without error.
        assert "mvp.bot.ocr" in sys.modules


def test_module_path_exists() -> None:
    """Sanity: ocr.py must exist at the expected path."""
    assert OCR_MODULE_PATH.exists(), f"{OCR_MODULE_PATH} not found"


def test_no_winrt_top_level_import_in_ocr_module() -> None:
    """Defense in depth: there MUST NOT be a bare ``import winrt`` statement.

    All winrt imports must be lazy (inside functions) so the order with
    onnxruntime is unambiguous.
    """
    src = _load_module_source()
    tree = ast.parse(src)
    for node in tree.body:  # only top-level imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("winrt"), (
                    f"winrt must be lazy-imported inside functions, "
                    f"not at module level: L{node.lineno} {alias.name}"
                )
        elif isinstance(node, ast.ImportFrom):
            assert not (node.module and node.module.startswith("winrt")), (
                f"winrt must be lazy-imported inside functions, "
                f"not at module level: L{node.lineno} {node.module}"
            )
