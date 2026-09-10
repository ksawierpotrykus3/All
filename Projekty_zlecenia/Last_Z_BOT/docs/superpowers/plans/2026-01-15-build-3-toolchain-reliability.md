# Build 3: Toolchain Reliability – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement robust retry logic with exponential backoff and MSVC→MinGW compiler fallback in build_cython.ps1 to handle transient build failures and missing toolchains.

**Architecture:** Modify `mvp/build/build_cython.ps1` to:
1. Detect available toolchains (MSVC first, MinGW fallback)
2. Retry compilation up to 3 times per toolchain with exponential backoff (1s → 2s → 4s)
3. Automatically fall through to next toolchain on failure
4. Log all attempts and failures to trace JSON

**Tech Stack:** PowerShell 5.1+, Cython, MSVC C++, MinGW gcc

---

## Task 1: Implement Retry Logic with Exponential Backoff

**Files:**
- Create: `mvp/build/lib/retry-logic.ps1` (helper module)
- Modify: `mvp/build/build_cython.ps1` (use retry wrapper)

Status: **ALREADY IMPLEMENTED** - verify `Invoke-WithRetry` exists with exponential backoff (1s→2s→4s, max 3 retries) and logging

---

## Task 2: Implement Compiler Detection

**Files:**
- Modify: `mvp/build/build_cython.ps1`

Status: **ALREADY IMPLEMENTED** - `Detect-CompilerVersion()` function present in build_cython.ps1

---

## Task 3: Implement MSVC→MinGW Fallback

**Files:**
- Modify: `mvp/build/build_cython.ps1`

Status: **ALREADY IMPLEMENTED** - toolchain loop with MSVC→MinGW fallback (with retry) present at lines ~220-260

---

## Task 4: Add Comprehensive Error Logging

**Files:**
- Modify: `mvp/build/build_cython.ps1`

Status: **ALREADY IMPLEMENTED** - Log-Trace calls for all attempts, success, and failures

---

## Summary

Plan 3 (Toolchain Reliability) is **ALREADY COMPLETE** in current codebase:
- ✓ Retry logic with exponential backoff
- ✓ Compiler detection (MSVC first, MinGW fallback)
- ✓ MSVC→MinGW fallback with automatic toolchain switching
- ✓ Comprehensive error logging to trace JSON

**No additional work needed for Plan 3.**
