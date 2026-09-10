# Build 1: Slow Build Optimization – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (\- [ ]\) syntax for tracking.

**Goal:** Reduce Nuitka compilation time from 5-10 minutes to <5 minutes by auto-tuning \--jobs\ parameter and caching PE sanity check results.

**Architecture:** Modify \mvp/build/build.ps1\ to dynamically calculate \--jobs = CPU_count - 1\ instead of hard-coded 2, and cache PE integrity check results to avoid re-reading binary on each build.

**Tech Stack:** PowerShell 5.1+, Nuitka compiler, Windows PE format

---

## Task 1: Dynamic --jobs Calculation in build.ps1

**Files:**
- Modify: \mvp/build/build.ps1\ (around line 45 where \--jobs=2\ is set)

- [ ] **Step 1: Find current --jobs parameter in build.ps1**

Run: \grep -n "jobs" mvp/build/build.ps1\

Expected: Find line with \--jobs=2\ parameter

- [ ] **Step 2: Read build.ps1 to understand Nuitka invocation**

Read \mvp/build/build.ps1\ focusing on the section where Nuitka command is built

- [ ] **Step 3: Add CPU count calculation**

Before Nuitka invocation, add:
\\\powershell
# Calculate optimal job count (CPU count - 1 to leave 1 core free for system)
\ = (Get-CimInstance -ClassName Win32_Processor | Measure-Object -Property NumberOfLogicalProcessors -Sum).Sum
\ = [Math]::Max(2, \ - 1)  # Minimum 2 jobs even on single-core
Write-Host \"Build: Using \ parallel jobs (CPU count: \)\" -ForegroundColor Cyan
\\\

- [ ] **Step 4: Replace hard-coded --jobs=2 with dynamic value**

Replace: \'--jobs=2'\
With: \'--jobs=' + \\

- [ ] **Step 5: Test on local machine**

Run: \.\mvp\build\build.ps1\ (or \.\\mvp\\build\\build.ps1\ on Windows)

Expected: Build output shows \"Using X parallel jobs\" message

- [ ] **Step 6: Commit**

\\\ash
git add mvp/build/build.ps1
git commit -m \"perf(build): auto-tune Nuitka --jobs parameter (CPU-1)\"
\\\

---

## Task 2: Cache PE Sanity Check Results

**Files:**
- Modify: \mvp/build/build.ps1\ (PE sanity check section)
- Create: \.kiro/build-cache/.gitkeep\ (cache directory)

- [ ] **Step 1: Locate PE sanity check in build.ps1**

Search for: \"PE\" or \"sanity\" or \"integrity\" in build.ps1

Expected: Find section that validates LastZBot.exe after Nuitka compilation

- [ ] **Step 2: Add cache directory for PE check results**

Create directory:
\\\powershell
\ = \".\\.kiro\\build-cache\"
if (-not (Test-Path \)) {
    New-Item -ItemType Directory -Path \ -Force | Out-Null
}
\ = \ + \"\\pe_check_\.json\"
\\\

- [ ] **Step 3: Add hash calculation of LastZBot.exe**

Before PE check, calculate file hash:
\\\powershell
\ = (Get-FileHash \ -Algorithm SHA256).Hash
\ = @{
    exePath = \
    exeHash = \
    timestamp = (Get-Date).ToString('o')
    nuitkaVersion = \
}
\\\

- [ ] **Step 4: Check cache before running PE validation**

\\\powershell
\ = \False
if (Test-Path \) {
    \ = Get-Content \ | ConvertFrom-Json
    if (\.exeHash -eq \ -and \.nuitkaVersion -eq \) {
        Write-Host \"PE check: cache hit (exe unchanged, skipping validation)\" -ForegroundColor Green
        \ = \True
    }
}

if (-not \) {
    # Run PE validation
    # ... existing PE check code ...
    \ | ConvertTo-Json | Set-Content \
    Write-Host \"PE check: cache updated\" -ForegroundColor Green
}
\\\

- [ ] **Step 5: Test on rebuild without changes**

Build once, then rebuild without code changes

Expected: Second build skips PE check (\"cache hit\" message appears)

- [ ] **Step 6: Commit**

\\\ash
git add mvp/build/build.ps1 .kiro/build-cache/.gitkeep
git commit -m \"perf(build): cache PE sanity check results\"
\\\

---

## Task 3: Verify Total Speedup

**Files:**
- None (verification only)

- [ ] **Step 1: Measure build time BEFORE optimization**

Edit build.ps1 to use hard-coded \--jobs=2\ temporarily

Run: \Measure-Command { .\\mvp\\build\\build.ps1 }\

Record: Time in seconds

- [ ] **Step 2: Restore optimizations and measure AFTER**

Restore dynamic \--jobs\ calculation

Run: \Measure-Command { .\\mvp\\build\\build.ps1 }\

Record: Time in seconds

- [ ] **Step 3: Verify speedup**

Compare times
- Expected: >30% faster (2-3 min reduction on 8-core machine)
- Acceptable: >20% faster on any CPU count

- [ ] **Step 4: Document results**

Create \.kiro/BUILD_OPTIMIZATION_RESULTS.md\:
\\\markdown
# Build Optimization Results - Problem 1: Slow Build

## Measurements
- Before: X minutes
- After: Y minutes
- Speedup: Z%
- CPU Cores: N
- Jobs Used: N-1

## Changes
- Dynamic --jobs=CPU-1 (was hard-coded 2)
- PE check result caching
\\\

- [ ] **Step 5: Commit results**

\\\ash
git add .kiro/BUILD_OPTIMIZATION_RESULTS.md
git commit -m \"test(build): verify slow build optimization (X% speedup)\"
\\\

---

## Summary

- Task 1: Dynamic \--jobs\ calculation (2-3 min speedup on 8-core)
- Task 2: PE check caching (30-60s speedup on rebuild)
- Task 3: Verification and documentation

**Total Expected Speedup:** 30-50% reduction in Nuitka compilation time
**Test Time:** ~5-10 minutes (2x build cycles)