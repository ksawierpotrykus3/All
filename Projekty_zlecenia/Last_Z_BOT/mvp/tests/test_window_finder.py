"""Tests for force_foreground window-focus helper and hwnd caching."""

from mvp.bot import window_finder as wf
from mvp.bot.window_finder import find_game_window, force_foreground


def test_force_foreground_returns_bool_for_missing_process():
    result = force_foreground("NonExistentProcess12345.exe")
    assert result is False


def test_find_game_window_cached_after_first_call(monkeypatch):
    wf._hwnd_cache.clear()
    wf._pid_cache.clear()
    calls = {"psutil_iter": 0}
    real_iter = wf.psutil.process_iter

    def counting_iter(attrs=None):
        calls["psutil_iter"] += 1
        return real_iter(attrs)

    monkeypatch.setattr(wf.psutil, "process_iter", counting_iter)

    proc_name = "NonExistentProcess12345.exe"
    result1 = find_game_window(proc_name)
    result2 = find_game_window(proc_name)
    result3 = find_game_window(proc_name)

    assert calls["psutil_iter"] <= 1, f"got {calls['psutil_iter']}"
    assert result1 is None and result2 is None and result3 is None


def test_refresh_window_geometry_rejects_invalid_hwnd():
    wf._hwnd_cache.clear()
    assert wf._refresh_window_geometry(99999999, 12345) is None


def test_refresh_window_geometry_rejects_hidden_window(monkeypatch):
    wf._hwnd_cache.clear()
    user32 = wf.user32
    monkeypatch.setattr(user32, "IsWindow", lambda _h: 1)
    monkeypatch.setattr(user32, "IsWindowVisible", lambda _h: 0)
    assert wf._refresh_window_geometry(12345, 0) is None


def test_refresh_window_geometry_rejects_minimized_window(monkeypatch):
    wf._hwnd_cache.clear()
    user32 = wf.user32

    def fake_gwtip(_hwnd, pid_ptr):
        pid_ptr._obj.value = 1234
        return 1

    monkeypatch.setattr(user32, "IsWindow", lambda _h: 1)
    monkeypatch.setattr(user32, "IsWindowVisible", lambda _h: 1)
    monkeypatch.setattr(user32, "GetWindowThreadProcessId", fake_gwtip)
    monkeypatch.setattr(user32, "IsIconic", lambda _h: 1)
    assert wf._refresh_window_geometry(12345, 1234) is None


def test_find_game_window_invalidates_cache_when_hwnd_becomes_invalid(monkeypatch):
    wf._hwnd_cache.clear()
    wf._pid_cache.clear()
    from mvp.bot.window_finder import WindowInfo

    stale_info = WindowInfo(
        hwnd=99999999,
        left=0,
        top=0,
        right=100,
        bottom=100,
        title="stale",
        title_bar_height=30,
    )
    wf._hwnd_cache["NonExistentProc.exe"] = (99999, wf.time.monotonic(), stale_info)

    monkeypatch.setattr(wf, "_find_process_pids_toolhelp", lambda _name: set())
    monkeypatch.setattr(wf.psutil, "process_iter", lambda _a=None: iter([]))

    result = find_game_window("NonExistentProc.exe")
    assert result is None
    entry = wf._hwnd_cache["NonExistentProc.exe"]
    assert entry[0] == 0, f"expected negative cache (pid=0), got pid={entry[0]}"
    assert entry[2] is None


def test_check_uipi_elevation_mismatch_false_when_bot_is_admin(monkeypatch):
    monkeypatch.setattr(wf, "is_bot_admin", lambda: True)
    assert wf.check_uipi_elevation_mismatch("Survival.exe") is False


def test_check_uipi_elevation_mismatch_detects_elevation(monkeypatch):
    monkeypatch.setattr(wf, "is_bot_admin", lambda: False)
    monkeypatch.setattr(wf, "_find_process_pids", lambda _name: {9999})

    class FakeKernel32:
        def OpenProcess(self, _access, _inherit, _pid):
            return 0

        def GetLastError(self):
            return 5

    monkeypatch.setattr(wf, "kernel32", FakeKernel32())
    assert wf.check_uipi_elevation_mismatch("Survival.exe") is True


def test_check_uipi_elevation_mismatch_false_when_accessible(monkeypatch):
    monkeypatch.setattr(wf, "is_bot_admin", lambda: False)
    monkeypatch.setattr(wf, "_find_process_pids", lambda _name: {9999})

    class FakeKernel32:
        def OpenProcess(self, _access, _inherit, _pid):
            return 12345

        def CloseHandle(self, _handle):
            return 1

    monkeypatch.setattr(wf, "kernel32", FakeKernel32())
    assert wf.check_uipi_elevation_mismatch("Survival.exe") is False


def test_find_process_pids_uses_toolhelp_not_process_iter(monkeypatch):
    """_find_process_pids must use Toolhelp32Snapshot, not psutil.process_iter."""
    wf._pid_cache.clear()

    def fake_toolhelp(name):
        return {1234}

    def boom_iter(*a, **k):
        raise AssertionError("psutil.process_iter must NOT be called when toolhelp works")

    monkeypatch.setattr(wf, "_find_process_pids_toolhelp", fake_toolhelp)
    monkeypatch.setattr(wf.psutil, "process_iter", boom_iter)

    assert wf._find_process_pids("Survival.exe") == {1234}


def test_pid_cache_ttl_respected(monkeypatch):
    """PID cache must be respected within _PID_CACHE_TTL_S (=10s)."""
    wf._pid_cache.clear()

    calls = {"n": 0}

    def counting_toolhelp(name):
        calls["n"] += 1
        return {5555}

    monkeypatch.setattr(wf, "_find_process_pids_toolhelp", counting_toolhelp)
    monkeypatch.setattr(wf.psutil, "pid_exists", lambda pid: True)

    wf._find_process_pids("Survival.exe")
    assert calls["n"] == 1
    wf._find_process_pids("Survival.exe")
    assert calls["n"] == 1