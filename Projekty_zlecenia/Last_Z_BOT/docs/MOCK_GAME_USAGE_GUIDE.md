> UWAGA: PRZESTARZAŁE — EasyOCR/Tesseract/Win7 usunięte. Patrz DIAGNOSTICS.md i WINDOWS7_SUPPORT.md.

# Mock Game Environment — Usage Guide

## Quick Start

### Run All Tests

```powershell
cd f:\PROJEKTY\joaxx
.\auto-test-dev-build-WITH-MOCK.ps1
```

**Expected Output:**
```
✅ ALL TESTS PASSED — Mock Game Environment Ready
```

### Run Specific Test Category

```powershell
# Integration tests only
.\auto-test-dev-build-WITH-MOCK.ps1 -Filter integration

# Macro tests only
.\auto-test-dev-build-WITH-MOCK.ps1 -Filter "macro"

# Game process tests only
.\auto-test-dev-build-WITH-MOCK.ps1 -Filter "game_process"
```

### Run From Python

```bash
# All mock game tests
uv run pytest mvp/test/mock_game/ mvp/test/test_with_mock_game/ -v

# Integration tests only
uv run pytest mvp/test/test_with_mock_game/test_integration_mock.py -v

# With coverage
uv run pytest mvp/test/mock_game/ mvp/test/test_with_mock_game/ --cov=mvp.test.mock_game
```

---

## Using Mock Game Components in Your Tests

### 1. Basic Game Process Usage

```python
from mvp.test.mock_game import MockGameProcess

def test_my_feature():
    # Create mock game
    game = MockGameProcess(width=1024, height=768)
    
    # Send clicks
    game.send_click(150, 150)
    
    # Get window info
    info = game.get_window_info()
    assert info.hwnd == 12345
    
    # Capture screenshot
    screenshot = game.capture_screenshot()
    assert screenshot[:4] == b'\x89PNG'
```

### 2. Macro Recording & Playback

```python
from mvp.test.mock_game import MockGameProcess, MacroEngine
import time

def test_macro_workflow():
    game = MockGameProcess()
    engine = MacroEngine()
    
    # Record macro
    engine.start_recording("my_macro")
    game.send_click(100, 100)
    time.sleep(0.026)
    game.send_click(150, 150)
    macro = engine.stop_recording(game)
    
    # Playback
    engine.playback_macro("my_macro", game)
    
    # Verify
    assert len(game.state['clicks']) == 2
```

### 3. Network Mocking

```python
from mvp.test.mock_game import NetworkMock

def test_network_workflow():
    network = NetworkMock()
    
    # Register response
    network.register_response("treasure.get", {
        "success": True,
        "reward": 100
    })
    
    # Get response
    response = network.get_response("treasure.get")
    assert response.success is True
    
    # Inject error
    network.inject_error("treasure.get", 500, "Server error")
    response = network.get_response("treasure.get")
    assert response.success is False
```

### 4. Screenshot Generation

```python
from mvp.test.mock_game import ScreenshotGenerator

def test_screenshot_workflow():
    gen = ScreenshotGenerator(width=1024, height=768)
    
    # Timer image
    timer_img = gen.generate_timer_image(minutes=4, seconds=30)
    assert len(timer_img) > 0
    
    # Chat image
    chat_img = gen.generate_chat_image(messages=["Hello", "World"])
    
    # Full screenshot
    full_img = gen.generate_game_screenshot(
        timer_minutes=5,
        timer_seconds=0,
        chat_messages=["Sample"],
        dialog_title="Alert"
    )
```

---

## Architecture

### Game Process Interface

All mock components implement `IGameProcess` interface:

```python
class IGameProcess(ABC):
    def get_window_info(self) -> WindowInfo:
        """Get window information"""
        pass
    
    def send_click(self, x: int, y: int, down: bool = True) -> bool:
        """Send click to game window"""
        pass
    
    def capture_screenshot(self) -> bytes:
        """Capture screenshot as PNG bytes"""
        pass
    
    def set_ui_state(self, key: str, value) -> None:
        """Set game state (timer, dialog open, etc)"""
        pass
    
    def get_ui_state(self, key: str):
        """Get game state"""
        pass
```

### Component Interaction

```
Test Code
    ↓
MockGameProcess (Layer 1)
    ├→ send_click()
    ├→ capture_screenshot()
    └→ set_ui_state()
         ↓
    ClickHandler (Layer 2)
    ClickWithTiming tracking
         ↓
    ScreenshotGenerator (Layer 3)
    PNG image generation
         ↓
    MacroEngine (Layer 4)
    Record/playback with timing
         ↓
    NetworkMock (Layer 5)
    API response simulation
```

---

## Performance Characteristics

### Execution Speed
- Single test: ~50ms
- Full suite (50 tests): ~26 seconds
- Overhead from easyocr: ~15 seconds (OCR tests)

### Resource Usage
- Memory: <100MB
- CPU: Single-threaded
- No GPU required

### Network Simulation
- Response delay: Configurable (0-5000ms)
- Error injection: Per-endpoint
- Offline fallback: Cached responses

---

## Troubleshooting

### Tests Fail with "ModuleNotFoundError"

```bash
# Re-sync dependencies
uv sync --extra dev
```

### Screenshot Tests Slow

easyocr loads ML models on first use. This is normal for OCR tests.
Subsequent runs are faster (cached models).

### Fixture Not Found

Ensure `conftest.py` is in the test directory:
```
mvp/test/mock_game/conftest.py
```

### Win32 Errors

Mock components use fake WinAPI (no actual Windows calls).
If you get "HWND not found", it's expected—HWND is simulated (value: 12345).

---

## CI/CD Integration

### GitHub Actions Example

```yaml
- name: Run Mock Game Tests
  run: |
    cd f:\PROJEKTY\joaxx
    .\auto-test-dev-build-WITH-MOCK.ps1
```

### GitLab CI Example

```yaml
test_mock_game:
  script:
    - cd f:\PROJEKTY\joaxx
    - uv run pytest mvp/test/mock_game/ mvp/test/test_with_mock_game/ -v
  timeout: 60 minutes
```

### Jenkins Example

```groovy
stage('Mock Game Tests') {
    steps {
        dir('f:\\PROJEKTY\\joaxx') {
            powershell '.\\auto-test-dev-build-WITH-MOCK.ps1'
        }
    }
}
```

---

## Adding New Tests

### Integration Test Template

```python
def test_my_workflow(mock_game_process):
    """Test: [What] -> [What] -> [What] (T#.#)
    
    Validates: Requirements X.Y - [Requirement description]
    """
    game = mock_game_process
    
    # Setup
    game.set_ui_state('timer_seconds', 300)
    
    # Execute
    game.send_click(150, 150)
    
    # Verify
    assert len(game.state['clicks']) == 1
```

### Use pytest Fixtures

```python
@pytest.fixture
def mock_game_process():
    """Provide a MockGameProcess instance for testing"""
    return MockGameProcess()

@pytest.fixture
def network_mock():
    """Provide a NetworkMock instance"""
    return NetworkMock()

def test_my_test(mock_game_process, network_mock):
    # Your test here
    pass
```

---

## Next Steps

1. **CI/CD Integration:** Deploy automation script to pipeline
2. **Chaos Testing:** Add random failures and network errors
3. **Performance Testing:** Measure click throughput under load
4. **Visual Regression:** Compare generated screenshots to baselines
5. **Real Game Testing:** Use mock as baseline for comparison with real game

---
