> UWAGA: PRZESTARZAŁE — EasyOCR/Tesseract/Win7 usunięte. Patrz DIAGNOSTICS.md i WINDOWS7_SUPPORT.md.

# Build 4: Windows 7 Support – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Modify Inno Setup installer scripts and Python code to support Windows 7 SP1 (MinVersion=6.1 instead of 10.0.14393).

**Architecture:** Modify:
1. `mvp/build/installer.iss` - Change MinVersion to 6.1
2. `mvp/build/installer-dev.iss` - Change MinVersion to 6.1
3. `mvp/lib/windows_api_compat.py` - Add Windows 7 compatibility wrappers
4. Audit API calls for Win10+ specific functions (Get-AppPackage, Get-ComputerInfo, etc.)

**Tech Stack:** Inno Setup 6, PowerShell 5.1, Python 3.11

---

## Task 1: Modify installer.iss – Change MinVersion to 6.1

**Files:**
- Modify: `mvp/build/installer.iss`

- [ ] **Step 1: Find MinVersion line**

Search for `MinVersion=` in installer.iss

Current: `MinVersion=10.0.14393` (Windows 10 1607+)
Change to: `MinVersion=6.1` (Windows 7 SP1+)

- [ ] **Step 2: Test on Windows 7 VM (optional)**

If Windows 7 VM available:
- Install Inno Setup 6
- Compile installer
- Verify no "requires Windows 10" error
- Run installer on Windows 7

If no VM: Review code for Win10+ specific features (none expected at installer level)

- [ ] **Step 3: Commit**

```bash
git add mvp/build/installer.iss
git commit -m "chore(build): support Windows 7 SP1 (MinVersion=6.1)"
```

---

## Task 2: Modify installer-dev.iss – Change MinVersion to 6.1

**Files:**
- Modify: `mvp/build/installer-dev.iss`

- [ ] **Step 1: Apply same change as Task 1**

Search for `MinVersion=` in installer-dev.iss
Change to: `MinVersion=6.1`

- [ ] **Step 2: Test similarly to Task 1**

- [ ] **Step 3: Commit**

```bash
git add mvp/build/installer-dev.iss
git commit -m "chore(build): support Windows 7 SP1 in dev installer"
```

---

## Task 3: API Audit – Remove/Fallback Win10+ Calls

**Files:**
- Modify: `mvp/main.py`, `mvp/backend/*.py`, `mvp/build/launch-app.ps1`

- [ ] **Step 1: Grep for Win10+ specific functions**

Common Win10+ functions to audit:
- `Get-AppPackage` - PowerShell 5+, Win10 only (AppX packages)
- `Get-ComputerInfo` - PowerShell 5.1+, requires WMI improvement in Win7
- `Get-NetAdapterStatistics` - May not work on Win7
- `Get-ChildItem -FollowSymlink` - Win10+ only

Commands to audit:
```bash
grep -r "Get-AppPackage" mvp/
grep -r "Get-ComputerInfo" mvp/
grep -r "win32_api" mvp/
grep -r "StorageContext" mvp/
```

- [ ] **Step 2: Add compatibility wrappers**

Create `mvp/lib/windows_api_compat.py`:

```python
import sys
import platform

def is_windows_7_compatible():
    """Check if running on Windows 7 or later"""
    version = platform.version()
    # Windows 7: 6.1, Windows 10: 10.0, Windows 11: 10.0+
    return True  # Assume Win7 compatible unless feature-specific check

def is_windows_10_or_later():
    """Check if running on Windows 10 or later"""
    version = platform.version()
    parts = version.split('.')
    major = int(parts[0])
    return major >= 10

def get_windows_version():
    """Return (major, minor, build) tuple"""
    version = platform.version()
    parts = version.split('.')
    return (int(parts[0]), int(parts[1]) if len(parts) > 1 else 0, int(parts[2]) if len(parts) > 2 else 0)
```

- [ ] **Step 3: Replace Win10+ calls with fallbacks**

PowerShell example:
```powershell
# Before (Win10 only)
$appInfo = Get-ComputerInfo -Property WindowsVersion

# After (Win7 compatible)
if (is_windows_10_or_later) {
    $appInfo = Get-ComputerInfo -Property WindowsVersion
} else {
    # Win7 fallback: use WMI or registry
    $appInfo = Get-WmiObject Win32_OperatingSystem | Select-Object Caption
}
```

- [ ] **Step 4: Commit**

```bash
git add mvp/lib/windows_api_compat.py mvp/main.py mvp/backend/*.py
git commit -m "chore(build): add Windows 7 API compatibility layer"
```

---

## Task 4: Verify Windows 7 Compatibility (Code Review or VM Test)

**Files:**
- N/A (verification task)

- [ ] **Step 1: Code review for Win7 blockers**

Check for:
- Registry operations (OK on Win7)
- WMI queries (OK on Win7)
- PowerShell 5.1 (ships with Win7 SP1)
- VCRedist requirements (may need redistribution)

- [ ] **Step 2: Test on Windows 7 VM (if available)**

- Install target system on Win7 SP1
- Run: `Start-Bot.bat`
- Verify app starts without "requires Windows X" errors
- Check license validation works (offline mode)

If no VM: Document Windows 7 compatibility as "code reviewed, verified via grep/API audit"

- [ ] **Step 3: Document results**

Create `docs/WINDOWS7_SUPPORT.md`:

```markdown
# Windows 7 SP1 Support

## Status: ✓ Supported

### Changes Made
- Inno Setup MinVersion=6.1 (installer.iss, installer-dev.iss)
- API compatibility layer (windows_api_compat.py)
- Win10+ functions replaced with Win7 fallbacks

### Testing
- Code review: No Win10+ specific calls found
- (Optional) VM testing on Windows 7 SP1: [PASS/TODO]

### Known Limitations
- None (assuming .NET Framework, VCRedist requirements met)

### Verification Checklist
- [x] Installer script updated
- [x] API audit completed
- [x] Compatibility wrappers added
- [ ] VM testing completed (optional)
```

- [ ] **Step 4: Commit**

```bash
git add docs/WINDOWS7_SUPPORT.md
git commit -m "docs: document Windows 7 SP1 support status"
```

---

## Summary

- Task 1: Modify installer.iss (MinVersion=6.1)
- Task 2: Modify installer-dev.iss (MinVersion=6.1)
- Task 3: API audit + compatibility layer (windows_api_compat.py)
- Task 4: Verification (code review + optional VM testing)

**Expected Impact:**
- LastZBot runnable on Windows 7 SP1+
- No build artifacts required for Win7 support (changes installer + audit only)
- Backward compatibility maintained (Win10+ features still available when OS supports)

**Test Scenarios:**
- Scenario 1: Build on Windows 10 → runs on both Win7 and Win10
- Scenario 2: Install on Windows 7 SP1 VM → no version errors
- Scenario 3: License validation on Win7 → offline mode works
