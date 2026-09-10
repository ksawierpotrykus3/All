> UWAGA: PRZESTARZAŁE — EasyOCR/Tesseract/Win7 usunięte. Patrz DIAGNOSTICS.md i WINDOWS7_SUPPORT.md.

# Build 2: Dependency Caching – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement persistent caching for vendor dependencies (EasyOCR models, Tesseract) and Cython .pyd artifacts to avoid re-downloading and re-compiling on unchanged code.

**Architecture:** Create \endor/manifest.json\ with SHA256 hashes for each downloaded dependency, and implement cache key logic in \uild_cython.ps1\ to skip recompilation if .pyx unchanged and compiler version matches.

**Tech Stack:** PowerShell 5.1+, SHA256 hashing, JSON manifest format

---

## Task 1: Create Vendor Manifest with SHA256 Hashes

**Files:**
- Create: \endor/manifest.json\
- Modify: \mvp/build/fetch-vendor.ps1\

- [ ] **Step 1: Create vendor/manifest.json template**

Create \endor/manifest.json\:
\\\json
{
  "version": "1.0",
  "timestamp": "2026-01-15T12:00:00Z",
  "dependencies": {
    "craft_mlt_25k.zip": {
      "sha256": "abc123...",
      "url": "https://...",
      "size_bytes": 1234567,
      "cached": true
    },
    "english_g2.zip": {
      "sha256": "def456...",
      "url": "https://...",
      "size_bytes": 2345678,
      "cached": true
    },
    "tesseract_installer.exe": {
      "sha256": "ghi789...",
      "url": "https://...",
      "size_bytes": 3456789,
      "cached": true
    }
  }
}
\\\

- [ ] **Step 2: Modify fetch-vendor.ps1 to compute and store SHA256**

Before: \if (Test-Path \) { Write-Host "skip (exists)" }\

After: Add hash validation:
\\\powershell
if (Test-Path \) {
    \ = (Get-FileHash \ -Algorithm SHA256).Hash
    \ = Get-Content 'vendor/manifest.json' | ConvertFrom-Json
    
    if (\.dependencies[\].sha256 -eq \) {
        Write-Host \"skip (exists, hash valid)\" -ForegroundColor Green
        return
    } else {
        Write-Host \"hash mismatch, re-downloading...\" -ForegroundColor Yellow
        Remove-Item \
    }
}
\\\

- [ ] **Step 3: After download, compute and update manifest**

After successful download:
\\\powershell
\ = (Get-FileHash \ -Algorithm SHA256).Hash
\.dependencies[\].sha256 = \
\.dependencies[\].cached = \True
\.timestamp = (Get-Date).ToString('o')
\ | ConvertTo-Json -Depth 10 | Set-Content 'vendor/manifest.json'
\\\

- [ ] **Step 4: Test fetch-vendor.ps1**

Run: \.\mvp\build\fetch-vendor.ps1\

Expected: 
- First run: Downloads all, creates manifest.json with hashes
- Second run: Skips download (\"hash valid\" message)

- [ ] **Step 5: Commit**

\\\ash
git add mvp/build/fetch-vendor.ps1 vendor/manifest.json
git commit -m \"feat(build): add vendor dependency manifest with SHA256 hashing\"
\\\

---

## Task 2: Implement .pyd Caching in build_cython.ps1

**Files:**
- Create: \.kiro/build-cache/cython-cache.json\
- Modify: \mvp/build/build_cython.ps1\

- [ ] **Step 1: Create cython cache directory and index**

Create \.kiro/build-cache/cython-cache.json\:
\\\json
{
  "version": "1.0",
  "cython_entries": {}
}
\\\

- [ ] **Step 2: Modify build_cython.ps1 to calculate .pyx file hash**

Before compiling each .pyx file:
\\\powershell
\ = Get-Item \
\ = (Get-FileHash \.FullName -Algorithm SHA256).Hash
\ = \.LastWriteTime.ToString('o')
\ = & cython --version 2>&1 | Select-Object -First 1

\ = @{
    filename = \.Name
    hash = \
    cython_version = \
    timestamp = (Get-Date).ToString('o')
}
\\\

- [ ] **Step 3: Check cache before compilation**

\\\powershell
\ = Get-Content '.kiro/build-cache/cython-cache.json' | ConvertFrom-Json
\ = \.cython_entries[\.Name]

if (\ -and \.hash -eq \ -and \.cython_version -eq \) {
    Write-Host \"Cython: \ cache hit, skipping compilation\" -ForegroundColor Green
    # Copy cached .pyd from artifact directory
    Copy-Item \".kiro/build-cache/artifacts/\.pyd\" \ -Force
    return
}
\\\

- [ ] **Step 4: After compilation, cache the .pyd artifact**

\\\powershell
# Store .pyd in artifact cache
\ = '.kiro/build-cache/artifacts'
if (-not (Test-Path \)) { New-Item -ItemType Directory -Path \ -Force | Out-Null }
Copy-Item \ \"\/\.pyd\" -Force

# Update cache index
\.cython_entries[\.Name] = \
\ | ConvertTo-Json -Depth 10 | Set-Content '.kiro/build-cache/cython-cache.json'
Write-Host \"Cython: Compilation cached\" -ForegroundColor Green
\\\

- [ ] **Step 5: Test build_cython.ps1**

Run: \.\mvp\build\build_cython.ps1\

Expected:
- First run: Compiles all .pyx files, caches .pyd artifacts
- Second run (no code changes): \"cache hit\" messages appear, no recompilation
- Second run (after .pyx edit): Recompiles affected file

- [ ] **Step 6: Commit**

\\\ash
git add mvp/build/build_cython.ps1 .kiro/build-cache/cython-cache.json
git commit -m \"feat(build): implement cython .pyd artifact caching\"
\\\

---

## Task 3: Cache Invalidation Strategy

**Files:**
- Modify: \mvp/build/build.ps1\

- [ ] **Step 1: Add cache invalidation on version change**

In \uild.ps1\, detect version changes:
\\\powershell
\ = '.kiro/build-cache/build-version.txt'
\ = '1.0.0'  # From version.py or config

if (Test-Path \) {
    \ = Get-Content \
    if (\ -ne \) {
        Write-Host \"Version changed (\ -> \), clearing cache...\" -ForegroundColor Yellow
        Remove-Item '.kiro/build-cache/*' -Recurse -Force -ErrorAction SilentlyContinue
    }
}

\ | Set-Content \
\\\

- [ ] **Step 2: Add --clean-cache flag to build.ps1**

Support manual cache clear:
\\\powershell
param(
    [switch]\ = \False
)

if (\) {
    Write-Host \"Cleaning build cache...\" -ForegroundColor Cyan
    Remove-Item '.kiro/build-cache/*' -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Path '.kiro/build-cache' -Force | Out-Null
}
\\\

- [ ] **Step 3: Test cache invalidation**

Run: \.\mvp\build\build.ps1 -CleanCache\

Expected: Cache directory cleared

- [ ] **Step 4: Commit**

\\\ash
git add mvp/build/build.ps1
git commit -m \"feat(build): add cache invalidation strategy and --clean-cache flag\"
\\\

---

## Task 4: Add cache status to build output

**Files:**
- Modify: \mvp/build/build.ps1\

- [ ] **Step 1: Report cache statistics**

After build completes:
\\\powershell
Write-Host \"\"
Write-Host \"=== Build Cache Statistics ===\"
\ = 0
\ = 0
# Count cache hits from manifest
# Count cache hits from cython
Write-Host \"Cache Hits: \ / \\"
Write-Host \"Cache Location: .kiro/build-cache\"
Write-Host \"Total Cache Size: \\"
\\\

- [ ] **Step 2: Test and commit**

Run: \.\mvp\build\build.ps1\

Expected: Cache statistics appear at end of build

\\\ash
git add mvp/build/build.ps1
git commit -m \"feat(build): add cache statistics reporting\"
\\\

---

## Summary

- Task 1: Vendor manifest with SHA256 (skip re-download on hash match)
- Task 2: Cython .pyd artifact caching (skip recompile if unchanged)
- Task 3: Cache invalidation strategy (version change, --clean-cache)
- Task 4: Cache statistics reporting

**Expected Impact:** 
- Second build (no code changes): 1-2 minutes (was 3-5 min)
- Skip vendor downloads: 1-2 min saved
- Skip cython compile: 2-3 min saved

**Total:** ~50-60% faster rebuild time