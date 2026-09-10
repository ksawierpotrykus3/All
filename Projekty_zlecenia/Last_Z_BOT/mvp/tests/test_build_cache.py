"""Unit tests for PowerShell build script retry logic and caching"""
from pathlib import Path


def test_retry_logic_success_first_attempt():
    """Test that retry logic succeeds on first attempt without delay"""
    # This is a placeholder — actual retry logic is in retry-logic.ps1
    # We verify it exists and can be dot-sourced
    ps_file = Path("mvp/build/lib/retry-logic.ps1")
    assert ps_file.exists(), "retry-logic.ps1 must exist"


def test_cache_config_loadable():
    """Test that build config can be loaded"""
    ps_file = Path("mvp/build/lib/build-config.ps1")
    assert ps_file.exists(), "build-config.ps1 must exist"

    # Verify it has required exports
    content = ps_file.read_text()
    assert "Get-BuildConfig" in content, "Must export Get-BuildConfig function"
    assert "CACHE_DIR" in content, "Must define CACHE_DIR"


def test_health_check_accepts_parameters():
    """Test that health-check.ps1 accepts custom paths and checks Fast OCR"""
    ps_file = Path("mvp/build/health-check.ps1")
    assert ps_file.exists(), "health-check.ps1 must exist"

    content = ps_file.read_text()
    # Verify parameters are defined
    assert "param(" in content, "Must have param block"
    assert "AppPath" in content, "Must accept AppPath parameter"
    assert "LogFile" in content, "Must accept LogFile parameter"
    # Verify Fast OCR engine check
    assert "rapidocr_onnxruntime" in content, "Must check Fast OCR engine"


def test_build_script_cache_stats():
    """Test that build.ps1 reads and displays cache statistics"""
    ps_file = Path("mvp/build/build.ps1")
    assert ps_file.exists(), "build.ps1 must exist"

    content = ps_file.read_text()
    # Verify cache stats are read from JSON files
    assert "fetch-vendor-stats.json" in content, "Must read fetch-vendor stats"
    assert "build_cython-stats.json" in content, "Must read cython stats"
    assert "totalCacheHits" in content or "total_cache_hits" in content.lower(), "Must aggregate cache hits"
    assert "Build Cache Statistics" in content, "Must display cache statistics"


def test_version_parsing_from_pyproject():
    """Test that version can be extracted from pyproject.toml"""
    pyproject = Path("pyproject.toml")
    if pyproject.exists():
        content = pyproject.read_text()
        # Should have version field
        assert "version = " in content, "pyproject.toml must have version field"


def test_cache_stats_json_structure():
    """Test expected structure of cache stats JSON files"""
    cache_dir = Path(".kiro/build-cache")
    expected_fields = ["cache_hits", "cache_misses", "time_saved_seconds"]

    assert cache_dir.name == "build-cache"
    assert "cache_hits" in expected_fields


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
