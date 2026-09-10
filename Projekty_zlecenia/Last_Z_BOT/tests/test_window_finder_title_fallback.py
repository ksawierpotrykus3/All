from mvp.bot.window_finder import _find_window_by_title, WindowInfo


def test_find_window_by_title_returns_none_when_absent(monkeypatch):
    def fake_enum(proc, lparam):
        return True
    monkeypatch.setattr("mvp.bot.window_finder.user32.EnumWindows", fake_enum)
    assert _find_window_by_title("Brak takiego okna") is None


def test_find_window_by_title_returns_window(monkeypatch):
    def fake_enum(proc, lparam):
        # Call the callback with a dummy hwnd and the same lparam.
        # The callback returns False when it finds a match, stopping enumeration.
        return proc(42, lparam)

    monkeypatch.setattr("mvp.bot.window_finder.user32.EnumWindows", fake_enum)
    monkeypatch.setattr("mvp.bot.window_finder.user32.IsWindowVisible", lambda hwnd: True)
    monkeypatch.setattr(
        "mvp.bot.window_finder._get_window_title", lambda hwnd: "LastZ Simulator"
    )
    monkeypatch.setattr(
        "mvp.bot.window_finder._refresh_window_geometry",
        lambda hwnd, pid: WindowInfo(hwnd, 0, 0, 800, 600, "LastZ Simulator", 0),
    )
    result = _find_window_by_title("LastZ Simulator")
    assert result is not None
    assert result.title == "LastZ Simulator"