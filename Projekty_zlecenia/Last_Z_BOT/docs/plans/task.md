| Task | Status | Notes |
|---|---|---|
| Phase 1: Root Cause Investigation | Completed | Root cause identified: parents[3] in game.py:25 points to F:\PROJEKTY instead of repo root F:\PROJEKTY\joaxx |
| Phase 2: Pattern Analysis | Completed | Verified data/macro_testing exists at repo root; BotBridge missing connect_to_bot / metrics integration |
| Phase 3: Hypothesis and Testing | Completed | Verified hypothesis with failing test on image loading; confirmed fix on test_game_simulator_module |
| Phase 4: Implementation & Verification | Completed | Fixed data_dir resolution, added fallback placeholders, wired BotBridge to connect_to_bot and metrics, 175/175 tests passed |
| Debugging Macro ROI & Arrow Detection | Completed | Verified arrow detection on 1_scan_chat_with_arrow.png at (1176, 937) s=0.9725 in ROI [1114, 870, 1220, 986]; generated visual artifacts |
| Fix & Test _ROI_ALLIANCE_TAB | Completed | Centered ROI [916, 59, 1007, 104] (91x45 px), fixed text clipping, score 0.959, 73/73 tests passed |
| Client-Space ROI Architecture Refactor | Completed | Eliminated 31px title-bar calibration debt; normalized all ROIs to client frame (0-100%); unified GameROI and WindowContext; 155/155 tests passed |
| Unity Spam Click Debugging & Research | Completed | Root causes identified: Win32 SendInput dx/dy ignored without MOVE, direct_first cursor position bug, bezier delay causing 0ms hold burst, Unity MobileTouchCamera 1.5px drag vs ClickDetector 5px threshold; documented in diagnoza_spam_click_unity_i_autoklikery.md |
| Unity Spam Click Fix & Verification | Completed | Cursor position initialized before first click in Clicker, t_spam_start synchronized to eliminate 0ms hold burst, direct_first=True wired into watch_timer T0 spam, test isolation fixed in test_clicker_200fps, 149/149 bot tests passed |
| Unity Spam Click Approach B - CPU & Timing Fix | Completed | 30 CPS 1-frame DOWN/UP, noise D >= 5.5px (ClickDetector bypass), CPU spinlock reduced >80%, UIPI admin check, 1273/1273 tests passed |
| Perf & Leak Fix: Win32 & Input Layer | Completed | Cached virtual screen metrics in SendInputBackend, fixed ctypes WINFUNCTYPE leak, adaptive spinlock yield (40/40 tests passed) |
| Perf & Leak Fix: ScreenCapture Synchronization | Completed | Synchronized camera.grab under lock, eliminated manual gc.collect() calls (12/12 tests passed) |
| Perf & Leak Fix: GUI Threads & Texture Buffers | Completed | Prevented event-log-flush thread explosion, optimized RGBA buffer reuse, handled start/stop abort (3/3 tests passed) |
| Perf & Leak Fix: Vision Cache & Macro Engine I/O | Completed | Cached multi-scale arrow templates, optimized checkpoint writing (108/108 tests passed) |
| Full Verification of 10 Perf Fixes | Completed | Dedicated test suite test_perf_optimizations (11/11 passed), regression suite (126/126 passed), ruff clean |
| Frida Profiling & Dual-Gate OCR Optimization | Completed | Eliminated 7.7s RapidOCR false positives from Bounty/Truck cards via precise hints + narrow ROI; killed 2 orphaned processes; test_perf_optimizations (12/12 passed), test_ocr (29/29 passed) |
| Debug Watch Timer CPU & Unity Spam Click | Completed | Root causes identified: TimerOCR lacks WinOCR/Dual-Gate, watch_timer loop has 1ms busy-wait when OCR takes ~100-200ms, SendInput dx/dy ignored without MOVE, Unity 15 FPS background throttling without focus buffer; research & benchmark in docs/02_ANALIZY/diagnoza_cpu_watch_timer_i_spam_click_unity.md |
| Implement Fast WinOCR in TimerOCR | Completed | Native Windows.Media.Ocr path reduces latency from 48ms to 6.67ms (7.2x speedup); 26/26 tests passed |
| Fix watch_timer Busy-Loop & Sleep Budget | Completed | Elapsed-based query timestamp, min_sleep floors, safe ClickerError handling; 12/12 tests passed |
| Stabilize Game Focus & 30 CPS in spam_click | Completed | force_foreground check + 35ms activation buffer, transient error tolerance; 24/24 tests passed |
| SendInputBackend Error Handling & Retries | Completed | Added GetLastError diagnostics and Error 5 detection; 130/130 bot tests passed |
| Fix Heli Alert False Triggers & Zero-Latency Click | Completed | Blacklist false cards (Bounty/Truck/Land/Share), clean hint_pattern, 80ms poll interval, zero-latency direct click in SCROLL_LISTEN_CHAT, full-card center click; 107/107 tests passed |
