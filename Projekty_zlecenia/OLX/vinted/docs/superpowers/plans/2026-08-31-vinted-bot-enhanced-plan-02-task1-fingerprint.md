## TASK 1: Enhanced Fingerprint Module

**Problem:** Current FF152 fingerprint works for detection but checkout returns 403 DataDome. Need full browser fingerprint + additional headers.

**Solution:** Create `fingerprint_enhancer.py` with complete browser fingerprint including TLS extensions, HTTP/2 settings, and browser-specific headers.

**Files:**
- Create: `bot/src/vintedbot/fingerprint_enhancer.py`
- Modify: `bot/src/vintedbot/config.py` (add constants)
- Test: `bot/tests/test_fingerprint_enhancer.py`

---

### Step 1: Create failing test for fingerprint enhancer

**File:** `bot/tests/test_fingerprint_enhancer.py`

```python
"""Tests for fingerprint_enhancer module."""
import pytest
from vintedbot.fingerprint_enhancer import EnhancedFingerprint


def test_enhanced_fingerprint_initialization():
    """Test that EnhancedFingerprint initializes with profile."""
    fp = EnhancedFingerprint(profile_id="firefox152_custom")
    assert fp.profile_id == "firefox152_custom"
    assert hasattr(fp, 'fingerprint_data')
    assert isinstance(fp.fingerprint_data, dict)


def test_enhanced_fingerprint_has_required_keys():
    """Test that fingerprint contains required TLS/HTTP keys."""
    fp = EnhancedFingerprint(profile_id="firefox152_custom")
    data = fp.fingerprint_data
    
    assert "ja3" in data
    assert "akamai" in data
    assert "tls_extensions" in data
    assert "http2_settings" in data
    assert "additional_headers" in data
    assert "user_agent" in data


def test_get_session_kwargs_returns_dict():
    """Test that get_session_kwargs returns valid curl_cffi parameters."""
    fp = EnhancedFingerprint(profile_id="firefox152_custom")
    kwargs = fp.get_session_kwargs()
    
    assert isinstance(kwargs, dict)
    assert "impersonate" in kwargs
    assert "ja3" in kwargs
    assert "akamai" in kwargs
    assert "extra_fp" in kwargs
    assert "headers" in kwargs
    
    # Verify headers contain required browser headers
    headers = kwargs["headers"]
    assert "Accept" in headers
    assert "Accept-Language" in headers
    assert "Sec-Fetch-Dest" in headers
    assert "Sec-Fetch-Mode" in headers
    assert "Sec-Fetch-Site" in headers


def test_different_profiles_produce_different_fingerprints():
    """Test that different profiles create different fingerprints."""
    fp1 = EnhancedFingerprint(profile_id="firefox152_custom_1")
    fp2 = EnhancedFingerprint(profile_id="firefox152_custom_2")
    
    kwargs1 = fp1.get_session_kwargs()
    kwargs2 = fp2.get_session_kwargs()
    
    # Should have same structure but potentially different values
    assert kwargs1.keys() == kwargs2.keys()
    # User agents might differ between profiles
    assert kwargs1["headers"]["User-Agent"] != kwargs2["headers"]["User-Agent"]
```

**Command to run test (should fail):**
```bash
cd f:\PROJEKTY\vinted\bot
pytest tests/test_fingerprint_enhancer.py -v
```

**Expected output:** FAIL with "ModuleNotFoundError: No module named 'vintedbot.fingerprint_enhancer'"

---

### Step 2: Add fingerprint constants to config

**File:** `bot/src/vintedbot/config.py` (append to end)

```python
# Enhanced fingerprint constants for Firefox 152
FF152_FULL_JA3 = "771,4865-4867-4866-49195-49199-52393-52392-49196-49200-49162-49171-49172-156-157-47-53,0-23-65281-10-11-35-16-5-34-18-51-43-13-45-28-27-65037,4588-29-23-24-25-256-257,0"
FF152_FULL_AKAMAI = "1:65536;2:0;4:131072;5:16384|12517377|0|m,p,a,s"

# Full TLS extensions for Firefox 152
FF152_FULL_TLS_EXTENSIONS = {
    "tls_delegated_credential": "ecdsa_secp256r1_sha256:ecdsa_secp384r1_sha384:ecdsa_secp521r1_sha512:ecdsa_sha1",
    "tls_record_size_limit": 16385,
    "tls_cert_compression": "zstd",
    "tls_signature_algorithms": [
        "ecdsa_secp256r1_sha256",
        "ecdsa_secp384r1_sha384",
        "ecdsa_secp521r1_sha512",
        "rsa_pss_rsae_sha256",
        "rsa_pss_rsae_sha384",
        "rsa_pss_rsae_sha512",
        "rsa_pkcs1_sha256",
        "rsa_pkcs1_sha384",
        "rsa_pkcs1_sha512",
        "ecdsa_sha1",
        "rsa_pkcs1_sha1",
    ],
    "tls_supported_groups": [
        "x25519", "secp256r1", "secp384r1", "secp521r1",
        "ffdhe2048", "ffdhe3072", "ffdhe4096", "ffdhe6144", "ffdhe8192"
    ],
    "tls_psk_key_exchange_modes": ["psk_dhe_ke"],
    "tls_application_settings": ["h2", "http/1.1"],
    "tls_key_share_curves": ["x25519", "secp256r1", "secp384r1"]
}

# HTTP/2 settings for Firefox 152
FF152_HTTP2_SETTINGS = {
    "HEADER_TABLE_SIZE": 65536,
    "ENABLE_PUSH": 1,
    "MAX_CONCURRENT_STREAMS": 1000,
    "INITIAL_WINDOW_SIZE": 6291456,
    "MAX_FRAME_SIZE": 16384,
    "MAX_HEADER_LIST_SIZE": 262144
}

# Browser headers template
BROWSER_HEADERS_TEMPLATE = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "pl,en-US;q=0.7,en;q=0.3",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0"
}
```

**Command to verify config changes:**
```bash
cd f:\PROJEKTY\vinted\bot
python -c "from src.vintedbot.config import FF152_FULL_TLS_EXTENSIONS; print('Config OK' if 'tls_signature_algorithms' in FF152_FULL_TLS_EXTENSIONS else 'FAIL')"
```

**Expected output:** "Config OK"

---

### Step 3: Create EnhancedFingerprint class (minimal)

**File:** `bot/src/vintedbot/fingerprint_enhancer.py`

```python
"""Enhanced browser fingerprint for curl_cffi with full TLS/HTTP2 support."""
import random
from typing import Dict, Any
from .config import (
    FF152_FULL_JA3, FF152_FULL_AKAMAI, FF152_FULL_TLS_EXTENSIONS,
    FF152_HTTP2_SETTINGS, BROWSER_HEADERS_TEMPLATE
)


class EnhancedFingerprint:
    """Enhanced browser fingerprint with full TLS/HTTP2 support."""
    
    def __init__(self, profile_id: str = "firefox152_custom"):
        self.profile_id = profile_id
        self.fingerprint_data = self._load_fingerprint_profile()
    
    def _load_fingerprint_profile(self) -> Dict[str, Any]:
        """Load complete fingerprint from profile."""
        return {
            "ja3": FF152_FULL_JA3,
            "akamai": FF152_FULL_AKAMAI,
            "tls_extensions": FF152_FULL_TLS_EXTENSIONS,
            "http2_settings": FF152_HTTP2_SETTINGS,
            "additional_headers": self._generate_additional_headers(),
            "user_agent": self._generate_user_agent()
        }
    
    def _generate_user_agent(self) -> str:
        """Generate Firefox user agent based on profile."""
        firefox_versions = ["152.0", "151.0", "150.0", "149.0"]
        windows_versions = ["10.0", "11.0"]
        
        version = random.choice(firefox_versions)
        windows = random.choice(windows_versions)
        
        return f"Mozilla/5.0 (Windows NT {windows}; Win64; x64; rv:{version}) Gecko/20100101 Firefox/{version}"
    
    def _generate_additional_headers(self) -> Dict[str, str]:
        """Generate additional browser-specific headers."""
        return {
            "DNT": "1",
            "Sec-GPC": "1",
            "Priority": "u=0, i",
            "Viewport-Width": str(random.randint(1366, 1920)),
            "Width": str(random.randint(1366, 1920))
        }
    
    def get_session_kwargs(self) -> Dict[str, Any]:
        """Return complete session parameters for curl_cffi."""
        headers = BROWSER_HEADERS_TEMPLATE.copy()
        headers.update(self.fingerprint_data["additional_headers"])
        headers["User-Agent"] = self.fingerprint_data["user_agent"]
        
        return {
            "impersonate": "firefox152",
            "ja3": self.fingerprint_data["ja3"],
            "akamai": self.fingerprint_data["akamai"],
            "extra_fp": self.fingerprint_data["tls_extensions"],
            "headers": headers
        }
    
    def get_fingerprint_summary(self) -> Dict[str, Any]:
        """Get summary of fingerprint for logging."""
        return {
            "profile_id": self.profile_id,
            "user_agent": self.fingerprint_data["user_agent"],
            "tls_extensions_count": len(self.fingerprint_data["tls_extensions"]),
            "http2_settings_count": len(self.fingerprint_data["http2_settings"])
        }
```

**Command to verify module creation:**
```bash
cd f:\PROJEKTY\vinted\bot
python -c "from src.vintedbot.fingerprint_enhancer import EnhancedFingerprint; fp = EnhancedFingerprint(); print('Module OK' if fp.profile_id == 'firefox152_custom' else 'FAIL')"
```

**Expected output:** "Module OK"

---

### Step 4: Run tests to verify they pass

**Command:**
```bash
cd f:\PROJEKTY\vinted\bot
pytest tests/test_fingerprint_enhancer.py -v
```

**Expected output:** All 4 tests PASS

---

### Step 5: Commit fingerprint module

**Command:**
```bash
cd f:\PROJEKTY\vinted\bot
git add src/vintedbot/fingerprint_enhancer.py src/vintedbot/config.py tests/test_fingerprint_enhancer.py
git commit -m "feat: Add EnhancedFingerprint module with full TLS/HTTP2 support

- EnhancedFingerprint class with complete browser fingerprint
- Full TLS extensions for Firefox 152
- HTTP/2 settings and browser headers
- Randomized user agent generation
- Tests for initialization and session parameters"
```

**Next task:** Integration with detection module