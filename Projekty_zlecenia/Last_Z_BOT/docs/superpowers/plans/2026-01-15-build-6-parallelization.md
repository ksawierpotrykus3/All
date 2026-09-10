# Build 6: Parallelization – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement parallel execution of fetch-vendor.ps1 and build_cython.ps1 using PowerShell jobs to reduce overall build time by ~30-40% (from sequential 5-7 min to parallel 3-5 min for these steps).

**Architecture:** Modify `mvp/build/build.ps1` to:
1. Start fetch-vendor and build_cython as parallel PowerShell jobs
2. Wait for both jobs to complete (with timeout)
3. Aggregate logs from both jobs into master trace.json
4. Handle errors from either job gracefully

**Tech Stack:** PowerShell 5.1+ (Start-Job, Wait-Job, Receive-Job), JSON log aggregation

---

## Task 1: Fix PowerShell Job Context Issues

**Current Status:** Sequential execution (jobs deferred due to path resolution issues in child jobs)

**Root Cause:** PowerShell jobs have different working directory context than parent process, causing path resolution failures in child scripts.

**Solution Options:**
1. Use `Invoke-Command -AsJob` with explicit path parameters
2. Pass absolute resolved paths in ArgumentList
3. Use `Push-Location` in child scripts before execution
4. Use ScriptBlock instead of FilePath in Start-Job

- [ ] **Step 1: Use absolute paths for child scripts**

```powershell
$fetchVendorScript = (Resolve-Path "mvp/build/fetch-vendor.ps1").Path
$buildCythonScript = (Resolve-Path "mvp/build/build_cython.ps1").Path

$fetchJob = Start-Job -FilePath $fetchVendorScript -ArgumentList $LogFile
$cythonJob = Start-Job -FilePath $buildCythonScript -ArgumentList $RepoRoot, $LogFile
```

- [ ] **Step 2: Ensure child scripts handle relative paths**

In fetch-vendor.ps1 and build_cython.ps1:
```powershell
$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$buildDir = $PSScriptRoot
# ... rest of script
```

- [ ] **Step 3: Test parallel execution**

Run: `.\mvp\build\build.ps1`

Expected output:
```
==> Step 1-2/4: Fetch vendor + Build Cython (parallel)
Starting fetch-vendor (job ID: 1)
Starting build_cython (job ID: 2)
Waiting for jobs to complete...
fetch-vendor job completed
build_cython job completed
```

- [ ] **Step 4: Commit**

```bash
git add mvp/build/build.ps1
git commit -m "feat(build): implement parallel fetch-vendor + build_cython with absolute paths"
```

---

## Task 2: Implement Job Result Aggregation

**Files:**
- Modify: `mvp/build/build.ps1`

- [ ] **Step 1: Collect outputs from both jobs**

```powershell
$fetchOutput = Receive-Job -Job $fetchJob -ErrorVariable fetchError
$cythonOutput = Receive-Job -Job $cythonJob -ErrorVariable cythonError
```

- [ ] **Step 2: Merge logs from parallel jobs**

Both child scripts should write to separate stats files:
- `.kiro/build-cache/fetch-vendor-stats.json`
- `.kiro/build-cache/build_cython-stats.json`

Parent script loads and displays both.

- [ ] **Step 3: Chronologically merge trace entries (optional)**

If each job writes to shared trace.json:
```powershell
# Child script appends with timestamp
# Parent script re-reads and sorts by timestamp at end
$allEntries = (Get-Content $LogFile | ConvertFrom-Json)
$sortedEntries = $allEntries | Sort-Object { $_.timestamp }
$sortedEntries | ConvertTo-Json -Depth 10 | Set-Content $LogFile
```

- [ ] **Step 4: Commit**

```bash
git add mvp/build/build.ps1
git commit -m "feat(build): aggregate logs from parallel jobs into master trace"
```

---

## Task 3: Implement Timeout and Error Handling

**Files:**
- Modify: `mvp/build/build.ps1`

- [ ] **Step 1: Add job timeout**

```powershell
$timeout = 600  # 10 minutes
Write-Host "Waiting for parallel jobs (timeout: $timeout seconds)..." -ForegroundColor Cyan
$completed = Wait-Job -Job @($fetchJob, $cythonJob) -Timeout $timeout

if (-not $completed) {
    Log-Trace "ERROR" "Jobs timeout exceeded" @{timeout = $timeout}
    Stop-Job -Job @($fetchJob, $cythonJob)
    throw "Build jobs exceeded timeout of $timeout seconds"
}
```

- [ ] **Step 2: Check job status**

```powershell
foreach ($job in @($fetchJob, $cythonJob)) {
    if ($job.State -eq "Failed") {
        Log-Trace "ERROR" "Job failed" @{job = $job.Name; error = $job.ChildJobs[0].JobStateInfo.Reason}
        throw "Job $($job.Name) failed"
    }
}
```

- [ ] **Step 3: Clean up jobs**

```powershell
Remove-Job -Job @($fetchJob, $cythonJob) -ErrorAction SilentlyContinue
```

- [ ] **Step 4: Commit**

```bash
git add mvp/build/build.ps1
git commit -m "feat(build): add timeout and error handling for parallel jobs"
```

---

## Task 4: Measure Parallelization Speedup

**Files:**
- N/A (measurement task)

- [ ] **Step 1: Measure sequential execution (baseline)**

```powershell
$seqStart = Get-Date
& (Join-Path $BuildDir 'fetch-vendor.ps1') -LogFile $LogFile
& (Join-Path $BuildDir 'build_cython.ps1') -LogFile $LogFile
$seqDuration = (Get-Date) - $seqStart
Write-Host "Sequential duration: $($seqDuration.TotalSeconds) seconds"
```

- [ ] **Step 2: Measure parallel execution**

```powershell
$parStart = Get-Date
# ... parallel job code ...
Wait-Job -Job @($fetchJob, $cythonJob)
$parDuration = (Get-Date) - $parStart
Write-Host "Parallel duration: $($parDuration.TotalSeconds) seconds"
```

- [ ] **Step 3: Calculate speedup**

```powershell
$speedup = $seqDuration.TotalSeconds / $parDuration.TotalSeconds
Write-Host "Speedup: $([Math]::Round($speedup, 2))x (~$([Math]::Round((1 - 1/$speedup) * 100, 0))% faster)"
```

Expected: ~1.5-2.0x speedup (30-50% faster)

- [ ] **Step 4: Document results**

Update `.kiro/BUILD_OPTIMIZATION_RESULTS.md` with parallelization metrics

- [ ] **Step 5: Commit**

```bash
git add .kiro/BUILD_OPTIMIZATION_RESULTS.md
git commit -m "test(build): measure Plan 6 parallelization speedup (1.5-2.0x expected)"
```

---

## Summary

- Task 1: Fix job context issues (absolute paths, $PSScriptRoot handling)
- Task 2: Aggregate logs from parallel jobs
- Task 3: Implement timeout and error handling
- Task 4: Measure parallelization speedup

**Expected Impact:**
- fetch-vendor + build_cython run in parallel (instead of sequential)
- Overall build time: 5-10 min → 3-7 min (30-40% faster for these steps)
- Complete visibility: all logs merged into master trace.json

**Test Scenarios:**
- Scenario 1: Both jobs succeed → parallel completion, merged logs
- Scenario 2: One job fails → error logged, build stops
- Scenario 3: Jobs timeout → graceful error, cleanup
- Scenario 4: Network/compile transient failure → retry logic handles
