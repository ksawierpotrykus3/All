# Sandbox Permission Errors During pytest

**Date**: 2026-09-03
**Scope**: Findings from `logs/` and `config.json` writes during pytest runs in the current sandboxed environment.

## Summary

Pytest discovered **53 PermissionError findings** across the test suite when run
under the current sandbox. The errors stem from the sandbox restricting writes
to system-wide `tmp_path` (`F:\Temp\pytest-of-Maksymilian`) and certain other
directories. Affected tests fall into three groups:

1. **GUI / config.json writes** (`test_main_window_save.py` and similar) —
   `Path("config.json")` resolves against the **current working directory**
   (the workspace root), and the sandbox denies writes there for some tests.
2. **Logs writes** — `mvp.bot.event_log.EventLogger` opens `logs/` under the
   workspace root. Some sandbox configurations deny access.
3. **`tmp_path` fixture itself** — pytest's default `tmp_path` factory tries
   to create `F:\Temp\pytest-of-<user>\...` and the sandbox returns
   `[WinError 5] Odmowa dostępu` (Access Denied).

## Symptom

```
PermissionError: [WinError 5] Odmowa dostępu: 'F:\\Temp\\pytest-of-Maksymilian'
File "F:\Temp\ps-script-...\Lib\os.py", line 175 in find_prefixed
  for x in os.scandir(root):
```

The error surfaces in **fixture setup** (before the test body runs), so even
read-only tests fail.

## Affected Tests (selected examples)

| Test file                            | Failure mode                                  |
|--------------------------------------|-----------------------------------------------|
| `mvp/tests/test_main_window_save.py` | `tmp_path` fixture fails during setup         |
| `mvp/tests/test_main_window_integration.py` (some) | `config.json` write denied     |
| `mvp/tests/test_logging_setup.py`    | `logs/` write denied                          |
| `mvp/tests/test_open_log_dir.py`     | `logs/` write denied                          |

In total **53 individual test failures** were attributed to this class of
error during the audit run (across the full suite, not just the new tests).

## Recommendation: use `tmp_path` for new tests (Phase 4 standard)

Per the AGENTS.md-aligned pytest config (`pyproject.toml`):

- The `tmp_path` fixture provides a **per-test** isolated directory that is
  automatically cleaned up.
- The recommended pattern is:
  ```python
  def test_x(tmp_path):
      out = tmp_path / "output.json"
      out.write_text("...")
  ```
- Avoid hard-coded `Path("config.json")`, `Path("logs/...")` paths in tests.
  Always resolve against `tmp_path` (or another fixture-managed directory).

## Phase 4 enforcement

All **new** tests created during this plan MUST:

1. Use the `tmp_path` fixture (or a similar workspace-local scratch fixture)
   for any filesystem writes.
2. Never write directly to `config.json` or `logs/` from inside a test.
3. If a fixture must be workspace-local, create a `.pytest_scratch/<test_name>/`
   subdirectory and `shutil.rmtree` it on teardown.

### Workaround used in `test_main_window_save.py`

Because the sandbox also denies `tmp_path` for new tests in this run, the file
uses a workspace-local `scratch_dir` fixture:

```python
@pytest.fixture
def scratch_dir():
    root = Path(__file__).resolve().parent.parent.parent / ".pytest_scratch" / "test_main_window_save"
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)
```

This is **acceptable** for the current sandbox but should be replaced with
`tmp_path` once the sandbox restriction is lifted.

## Related Audit Findings

- See `AUDIT_REPORT.md` §7 "Integration Test Issues" for the broader set of
  environment-related test failures (missing `plotly`, `rapidocr_onnxruntime`).
- The PermissionError class is independent of those dependency-missing failures.
