## TASK 3: Residential Proxy Manager

**Problem:** No residential proxy support for IP rotation and ban protection.

**Solution:** Create proxy manager with residential proxy rotation, health checks, cost monitoring, and integration with enhanced sessions.

**Files:**
- Create: `bot/src/vintedbot/proxy_manager.py`
- Modify: `bot/src/vintedbot/config.py` (add proxy config)
- Test: `bot/tests/test_proxy_manager.py`
- Create: `bot/config/providers/residential.yaml` (proxy provider configs)

---

### Step 1: Create proxy provider configuration

**File:** `bot/config/providers/residential.yaml`

```yaml
# Residential proxy provider configurations
providers:
  luminati:
    name: "Luminati"
    type: "residential"
    cost_per_gb: 12.50  # USD
    rotation: "session"  # session, request, timed
    health_check_url: "https://www.vinted.pl/api/v2/catalog/items"
    health_check_timeout: 10
    endpoints:
      - host: "zproxy.lum-superproxy.io"
        port: 22225
      - host: "brd.superproxy.io"
        port: 22225
    authentication: "user-pass"
    zones: ["pl", "de", "fr", "es", "it", "nl"]
  
  smartproxy:
    name: "Smartproxy"
    type: "residential"
    cost_per_gb: 15.00
    rotation: "request"
    health_check_url: "https://www.vinted.pl"
    health_check_timeout: 8
    endpoints:
      - host: "gate.smartproxy.com"
        port: 10000
    authentication: "user-pass"
    sticky_session: true
    session_duration: 1800  # 30 minutes
  
  oxylabs:
    name: "Oxylabs"
    type: "residential"
    cost_per_gb: 18.00
    rotation: "session"
    health_check_url: "https://api.vinted.pl/api/v2/catalog/items"
    health_check_timeout: 12
    endpoints:
      - host: "pr.oxylabs.io"
        port: 7777
    authentication: "user-pass"
    country_targeting: true

# Default configuration
default_provider: "luminati"
default_zone: "pl"
default_rotation_interval: 10  # requests
default_health_check_interval: 300  # 5 minutes

# Cost tracking
cost_tracking:
  enabled: true
  monthly_budget: 200.00  # USD
  alert_threshold: 0.8  # 80% of budget
  currency: "USD"
```

**Command to verify YAML file:**
```bash
cd f:\PROJEKTY\vinted\bot
python -c "import yaml; data = yaml.safe_load(open('config/providers/residential.yaml')); print('YAML OK' if data['default_provider'] == 'luminati' else 'FAIL')"
```

**Expected output:** "YAML OK" (if pyyaml installed, otherwise need to install)

---

### Step 2: Add proxy constants to config

**File:** `bot/src/vintedbot/config.py` (append)

```python
# Proxy configuration constants
PROXY_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "providers" / "residential.yaml"
PROXY_HEALTH_CHECK_TIMEOUT = 10
PROXY_ROTATION_INTERVAL = 10  # requests
PROXY_HEALTH_CHECK_INTERVAL = 300  # 5 minutes
PROXY_FAILURE_THRESHOLD = 3  # mark proxy dead after N failures
PROXY_SUCCESS_THRESHOLD = 5  # mark proxy healthy after N successes

# Proxy URL formats
PROXY_FORMATS = {
    "http": "http://{username}:{password}@{host}:{port}",
    "https": "http://{username}:{password}@{host}:{port}",
    "socks5": "socks5://{username}:{password}@{host}:{port}"
}
```

---

### Step 3: Create failing test for proxy manager

**File:** `bot/tests/test_proxy_manager.py`

```python
"""Tests for proxy_manager module."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import yaml
from vintedbot.proxy_manager import ResidentialProxyManager, ProxyEntry


def test_proxy_entry_initialization():
    """Test ProxyEntry initialization."""
    proxy_data = {
        "host": "proxy.example.com",
        "port": 8080,
        "username": "user123",
        "password": "pass456",
        "zone": "pl",
        "provider": "test_provider"
    }
    
    entry = ProxyEntry(**proxy_data)
    
    assert entry.host == "proxy.example.com"
    assert entry.port == 8080
    assert entry.username == "user123"
    assert entry.password == "pass456"
    assert entry.zone == "pl"
    assert entry.provider == "test_provider"
    assert entry.success_count == 0
    assert entry.failure_count == 0
    assert entry.last_used is None
    assert entry.is_healthy == True


def test_proxy_entry_url_generation():
    """Test proxy URL generation."""
    proxy_data = {
        "host": "proxy.example.com",
        "port": 8080,
        "username": "user123",
        "password": "pass456",
        "zone": "pl",
        "provider": "test_provider"
    }
    
    entry = ProxyEntry(**proxy_data)
    
    http_url = entry.get_url(protocol="http")
    assert http_url == "http://user123:pass456@proxy.example.com:8080"
    
    https_url = entry.get_url(protocol="https")
    assert https_url == "http://user123:pass456@proxy.example.com:8080"
    
    socks_url = entry.get_url(protocol="socks5")
    assert socks_url == "socks5://user123:pass456@proxy.example.com:8080"


def test_proxy_entry_health_tracking():
    """Test proxy health tracking."""
    proxy_data = {
        "host": "proxy.example.com",
        "port": 8080,
        "username": "user123",
        "password": "pass456",
        "zone": "pl",
        "provider": "test_provider"
    }
    
    entry = ProxyEntry(**proxy_data)
    
    # Initial state
    assert entry.is_healthy == True
    assert entry.success_count == 0
    assert entry.failure_count == 0
    
    # Record success
    entry.record_success()
    assert entry.success_count == 1
    assert entry.is_healthy == True
    
    # Record failures
    for _ in range(3):
        entry.record_failure()
    
    assert entry.failure_count == 3
    assert entry.is_healthy == False  # Should be marked unhealthy after 3 failures


@patch('pathlib.Path.exists')
@patch('yaml.safe_load')
def test_proxy_manager_initialization(mock_yaml_load, mock_exists):
    """Test ResidentialProxyManager initialization."""
    mock_exists.return_value = True
    mock_yaml_load.return_value = {
        "providers": {
            "luminati": {
                "name": "Luminati",
                "type": "residential",
                "endpoints": [{"host": "proxy.example.com", "port": 8080}]
            }
        },
        "default_provider": "luminati"
    }
    
    manager = ResidentialProxyManager(config_path="dummy_path.yaml")
    
    assert manager.config_path == "dummy_path.yaml"
    assert hasattr(manager, 'proxy_pool')
    assert hasattr(manager, 'provider_config')
    assert manager.default_provider == "luminati"


@patch('vintedbot.proxy_manager.ResidentialProxyManager._load_proxy_config')
def test_get_proxy_for_account(mock_load_config):
    """Test getting proxy for specific account."""
    mock_load_config.return_value = {
        "providers": {
            "luminati": {
                "name": "Luminati",
                "type": "residential",
                "endpoints": [{"host": "proxy.example.com", "port": 8080}]
            }
        },
        "default_provider": "luminati"
    }
    
    manager = ResidentialProxyManager()
    
    # Mock _select_optimal_proxy to return a test proxy
    test_proxy = Mock(
        host="proxy.example.com",
        port=8080,
        username="acc1_user",
        password="acc1_pass",
        get_url=Mock(return_value="http://acc1_user:acc1_pass@proxy.example.com:8080")
    )
    manager._select_optimal_proxy = Mock(return_value=test_proxy)
    
    proxy_config = manager.get_proxy_for_account(account_id="account_1", zone="pl")
    
    assert isinstance(proxy_config, dict)
    assert "http" in proxy_config
    assert "https" in proxy_config
    assert "proxy.example.com" in proxy_config["http"]


@patch('requests.get')
def test_proxy_health_check(mock_requests_get):
    """Test proxy health check functionality."""
    from vintedbot.proxy_manager import ResidentialProxyManager
    
    # Mock successful response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_requests_get.return_value = mock_response
    
    manager = ResidentialProxyManager()
    
    # Test with a mock proxy
    test_proxy = Mock(
        host="proxy.example.com",
        port=8080,
        username="test",
        password="test",
        get_url=Mock(return_value="http://test:test@proxy.example.com:8080"),
        is_healthy=True
    )
    
    is_healthy = manager._check_proxy_health(test_proxy)
    
    assert is_healthy == True
    mock_requests_get.assert_called_once()
    
    # Check that timeout and proxies were set correctly
    call_kwargs = mock_requests_get.call_args[1]
    assert call_kwargs['timeout'] == 10
    assert 'proxies' in call_kwargs
    assert 'proxy.example.com' in call_kwargs['proxies']['http']


def test_proxy_rotation_strategy():
    """Test proxy rotation strategies."""
    from vintedbot.proxy_manager import ResidentialProxyManager
    
    manager = ResidentialProxyManager()
    
    # Create test proxies
    test_proxies = [
        Mock(host=f"proxy{i}.example.com", port=8080, username="user", password="pass",
             is_healthy=True, last_used=None, success_count=i)
        for i in range(5)
    ]
    
    # Test round-robin selection
    selected = manager._round_robin_selection(test_proxies, account_id="test_account")
    assert selected in test_proxies
    
    # Test health-based selection (should pick healthy proxies)
    test_proxies[0].is_healthy = False
    selected = manager._health_based_selection(test_proxies)
    assert selected.is_healthy == True
    assert selected != test_proxies[0]
```

**Command to run proxy manager tests (should fail):**
```bash
cd f:\PROJEKTY\vinted\bot
pytest tests/test_proxy_manager.py -v
```

**Expected output:** FAIL with "ModuleNotFoundError: No module named 'vintedbot.proxy_manager'"

---

### Step 4: Create ProxyEntry data class

**File:** `bot/src/vintedbot/proxy_manager.py` (first part)

```python
"""Residential proxy manager with rotation, health checks, and cost tracking."""
import time
import random
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
import yaml

import requests
from curl_cffi import requests as creq

from .config import (
    PROXY_CONFIG_PATH, PROXY_HEALTH_CHECK_TIMEOUT,
    PROXY_ROTATION_INTERVAL, PROXY_HEALTH_CHECK_INTERVAL,
    PROXY_FAILURE_THRESHOLD, PROXY_SUCCESS_THRESHOLD,
    PROXY_FORMATS
)


@dataclass
class ProxyEntry:
    """Residential proxy entry with health tracking."""
    host: str
    port: int
    username: str
    password: str
    zone: str = "pl"
    provider: str = "unknown"
    success_count: int = 0
    failure_count: int = 0
    last_used: Optional[float] = None
    last_checked: Optional[float] = None
    is_healthy: bool = True
    cost_per_gb: float = 0.0
    data_used_mb: float = 0.0
    
    def get_url(self, protocol: str = "http") -> str:
        """Get proxy URL for given protocol."""
        if protocol not in PROXY_FORMATS:
            raise ValueError(f"Unsupported protocol: {protocol}. Supported: {list(PROXY_FORMATS.keys())}")
        
        return PROXY_FORMATS[protocol].format(
            username=self.username,
            password=self.password,
            host=self.host,
            port=self.port
        )
    
    def record_success(self):
        """Record successful proxy usage."""
        self.success_count += 1
        self.failure_count = 0
        self.last_used = time.time()
        self.is_healthy = True
        
        # Mark as healthy if enough successes
        if self.success_count >= PROXY_SUCCESS_THRESHOLD:
            self.is_healthy = True
    
    def record_failure(self):
        """Record proxy failure."""
        self.failure_count += 1
        self.success_count = 0
        self.last_used = time.time()
        
        # Mark as unhealthy if too many failures
        if self.failure_count >= PROXY_FAILURE_THRESHOLD:
            self.is_healthy = False
    
    def record_data_usage(self, bytes_used: int):
        """Record data usage for cost tracking."""
        self.data_used_mb += bytes_used / (1024 * 1024)  # Convert to MB
    
    def get_cost(self) -> float:
        """Calculate cost based on data usage."""
        return (self.data_used_mb / 1024) * self.cost_per_gb  # Convert MB to GB
    
    def needs_health_check(self) -> bool:
        """Check if proxy needs health check."""
        if self.last_checked is None:
            return True
        
        time_since_check = time.time() - self.last_checked
        return time_since_check > PROXY_HEALTH_CHECK_INTERVAL
    
    def __str__(self) -> str:
        """String representation of proxy."""
        return f"{self.provider}:{self.zone}@{self.host}:{self.port}"
```

**Command to verify ProxyEntry:**
```bash
cd f:\PROJEKTY\vinted\bot
python -c "from src.vintedbot.proxy_manager import ProxyEntry; proxy = ProxyEntry(host='test.com', port=8080, username='user', password='pass'); print('ProxyEntry OK' if proxy.host == 'test.com' else 'FAIL')"
```

**Expected output:** "ProxyEntry OK"

---

### Step 5: Create ResidentialProxyManager class

**File:** `bot/src/vintedbot/proxy_manager.py` (continued)

```python
class ResidentialProxyManager:
    """Manages residential proxies with rotation and health checks."""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or PROXY_CONFIG_PATH
        self.proxy_pool: Dict[str, List[ProxyEntry]] = {}
        self.provider_config: Dict[str, Any] = {}
        self.account_proxy_map: Dict[str, ProxyEntry] = {}
        self.health_check_running = False
        
        self._load_proxy_config()
        self._initialize_proxy_pool()
    
    def _load_proxy_config(self):
        """Load proxy configuration from YAML."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Proxy config not found: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        self.provider_config = config.get("providers", {})
        self.default_provider = config.get("default_provider", "luminati")
        self.default_zone = config.get("default_zone", "pl")
        self.rotation_interval = config.get("default_rotation_interval", PROXY_ROTATION_INTERVAL)
        self.health_check_interval = config.get("default_health_check_interval", PROXY_HEALTH_CHECK_INTERVAL)
        
        # Cost tracking config
        self.cost_config = config.get("cost_tracking", {})
        self.cost_tracking_enabled = self.cost_config.get("enabled", True)
        self.monthly_budget = self.cost_config.get("monthly_budget", 200.00)
    
    def _initialize_proxy_pool(self):
        """Initialize proxy pool from configuration."""
        for provider_name, provider_config in self.provider_config.items():
            self.proxy_pool[provider_name] = []
            
            endpoints = provider_config.get("endpoints", [])
            for endpoint in endpoints:
                # In real implementation, would fetch proxies from API
                # For now, create dummy entries
                proxy = ProxyEntry(
                    host=endpoint["host"],
                    port=endpoint["port"],
                    username=f"{provider_name}_user",  # Would be from config/API
                    password=f"{provider_name}_pass",
                    zone=self.default_zone,
                    provider=provider_name,
                    cost_per_gb=provider_config.get("cost_per_gb", 0.0)
                )
                self.proxy_pool[provider_name].append(proxy)
    
    def get_proxy_for_account(self, account_id: str, zone: Optional[str] = None) -> Dict[str, str]:
        """Get proxy configuration for specific account."""
        zone = zone or self.default_zone
        
        # Check if account already has assigned proxy
        if account_id in self.account_proxy_map:
            proxy = self.account_proxy_map[account_id]
            
            # Check if proxy needs rotation
            if proxy.needs_health_check() or not proxy.is_healthy:
                proxy = self._select_optimal_proxy(account_id, zone)
                self.account_proxy_map[account_id] = proxy
        else:
            # Select new proxy for account
            proxy = self._select_optimal_proxy(account_id, zone)
            self.account_proxy_map[account_id] = proxy
        
        proxy.last_used = time.time()
        
        return {
            "http": proxy.get_url("http"),
            "https": proxy.get_url("https")
        }
    
    def _select_optimal_proxy(self, account_id: str, zone: str) -> ProxyEntry:
        """Select optimal proxy for account based on health and zone."""
        provider = self.default_provider
        
        if provider not in self.proxy_pool:
            raise ValueError(f"Provider not found: {provider}")
        
        proxies = self.proxy_pool[provider]
        
        # Filter by health and zone
        healthy_proxies = [p for p in proxies if p.is_healthy and p.zone == zone]
        
        if not healthy_proxies:
            # Fallback to any healthy proxy
            healthy_proxies = [p for p in proxies if p.is_healthy]
        
        if not healthy_proxies:
            # Last resort: any proxy
            healthy_proxies = proxies
        
        # Simple round-robin selection
        index = hash(account_id) % len(healthy_proxies)
        return healthy_proxies[index]
    
    def _check_proxy_health(self, proxy: ProxyEntry) -> bool:
        """Check if proxy is healthy by making test request."""
        try:
            response = requests.get(
                "https://www.vinted.pl/api/v2/catalog/items",
                proxies={"http": proxy.get_url("http"), "https": proxy.get_url("https")},
                timeout=PROXY_HEALTH_CHECK_TIMEOUT
            )
            
            proxy.last_checked = time.time()
            
            if response.status_code == 200:
                proxy.record_success()
                return True
            else:
                proxy.record_failure()
                return False
                
        except Exception as e:
            proxy.last_checked = time.time()
            proxy.record_failure()
            return False
    
    def run_health_checks(self):
        """Run health checks on all proxies."""
        if self.health_check_running:
            return
        
        self.health_check_running = True
        
        try:
            for provider_proxies in self.proxy_pool.values():
                for proxy in provider_proxies:
                    if proxy.needs_health_check():
                        self._check_proxy_health(proxy)
        finally:
            self.health_check_running = False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get proxy manager statistics."""
        total_proxies = sum(len(proxies) for proxies in self.proxy_pool.values())
        healthy_proxies = sum(
            sum(1 for p in proxies if p.is_healthy)
            for proxies in self.proxy_pool.values()
        )
        
        total_cost = sum(proxy.get_cost() for proxies in self.proxy_pool.values() for proxy in proxies)
        
        return {
            "total_proxies": total_proxies,
            "healthy_proxies": healthy_proxies,
            "health_ratio": healthy_proxies / total_proxies if total_proxies > 0 else 0,
            "total_cost_usd": round(total_cost, 2),
            "monthly_budget": self.monthly_budget,
            "budget_used_percent": round((total_cost / self.monthly_budget) * 100, 2) if self.monthly_budget > 0 else 0,
            "accounts_with_proxies": len(self.account_proxy_map),
            "providers": list(self.proxy_pool.keys())
        }
    
    def rotate_account_proxy(self, account_id: str):
        """Force proxy rotation for account."""
        if account_id in self.account_proxy_map:
            del self.account_proxy_map[account_id]
        
        # Get new proxy
        self.get_proxy_for_account(account_id)
```

**Command to verify full proxy manager:**
```bash
cd f:\PROJEKTY\vinted\bot
python -c "from src.vintedbot.proxy_manager import ResidentialProxyManager; print('ProxyManager OK' if hasattr(ResidentialProxyManager, 'get_proxy_for_account') else 'FAIL')"
```

**Expected output:** "ProxyManager OK"

---

### Step 6: Run tests to verify they pass

**Command:**
```bash
cd f:\PROJEKTY\vinted\bot
pytest tests/test_proxy_manager.py -v
```

**Expected output:** All 6 tests PASS (after installing pyyaml if needed)

**Install pyyaml if missing:**
```bash
cd f:\PROJEKTY\vinted\bot
pip install pyyaml
```

---

### Step 7: Commit proxy manager

**Command:**
```bash
cd f:\PROJEKTY\vinted\bot
git add src/vintedbot/proxy_manager.py src/vintedbot/config.py config/providers/residential.yaml tests/test_proxy_manager.py
git commit -m "feat: Add ResidentialProxyManager with health checks and rotation

- ProxyEntry dataclass with health tracking and cost monitoring
- ResidentialProxyManager with proxy rotation per account
- YAML configuration for multiple proxy providers
- Health check system with automatic failure detection
- Cost tracking and budget monitoring
- Tests for proxy selection, health checks, and rotation"
```

**Next task:** Integrate proxy manager with enhanced sessions