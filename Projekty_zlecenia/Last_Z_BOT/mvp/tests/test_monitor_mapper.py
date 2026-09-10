"""Tests for monitor_mapper.validate_environment."""


from mvp.bot.monitor_mapper import validate_environment


def _run(width: int, height: int, monitors, dpi: int | None = 100):
    import mvp.bot.monitor_mapper as mm

    orig_monitors = mm._enum_monitors
    orig_dpi = mm._get_dpi_scale_percent
    mm._enum_monitors = lambda: monitors
    mm._get_dpi_scale_percent = lambda: dpi
    try:
        return validate_environment(width, height)
    finally:
        mm._enum_monitors = orig_monitors
        mm._get_dpi_scale_percent = orig_dpi


def test_single_monitor_16_9_100dpi_ok() -> None:
    monitors = [{"left": 0, "top": 0, "width": 1920, "height": 1080, "primary": True}]
    assert _run(1920, 1080, monitors, dpi=100) == []


def test_dpi_125_warns() -> None:
    monitors = [{"left": 0, "top": 0, "width": 1920, "height": 1080, "primary": True}]
    warnings = _run(1920, 1080, monitors, dpi=125)
    assert any("Skalowanie" in w for w in warnings)


def test_multi_monitor_different_resolution_warns() -> None:
    monitors = [
        {"left": 0, "top": 0, "width": 1920, "height": 1080, "primary": True},
        {"left": 1920, "top": 0, "width": 2560, "height": 1440, "primary": False},
    ]
    warnings = _run(1920, 1080, monitors, dpi=100)
    assert any("wiele monitorów" in w for w in warnings)


def test_multi_monitor_same_resolution_warns() -> None:
    """Dwa monitory 1920x1080 — także ostrzegamy (offset wirtualnego pulpitu)."""
    monitors = [
        {"left": 0, "top": 0, "width": 1920, "height": 1080, "primary": True},
        {"left": 1920, "top": 0, "width": 1920, "height": 1080, "primary": False},
    ]
    warnings = _run(1920, 1080, monitors, dpi=100)
    assert any("wiele monitorów" in w for w in warnings)


def test_unusual_aspect_ratio_warns() -> None:
    monitors = [{"left": 0, "top": 0, "width": 1920, "height": 1080, "primary": True}]
    warnings = _run(2560, 1080, monitors, dpi=100)  # ultrawide 21:9
    assert any("proporcje" in w for w in warnings)


def test_small_resolution_warns() -> None:
    monitors = [{"left": 0, "top": 0, "width": 1920, "height": 1080, "primary": True}]
    warnings = _run(1366, 768, monitors, dpi=100)
    assert any("rozdzielczość" in w for w in warnings)


def test_1440p_warns() -> None:
    """2560x1440 powinno ostrzegać, bo szablony są kalibrowane pod 1080p."""
    monitors = [{"left": 0, "top": 0, "width": 2560, "height": 1440, "primary": True}]
    warnings = _run(2560, 1440, monitors, dpi=100)
    assert any("rozdzielczość" in w for w in warnings)
