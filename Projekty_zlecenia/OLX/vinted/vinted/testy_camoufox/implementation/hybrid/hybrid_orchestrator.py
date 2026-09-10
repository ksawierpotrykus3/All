#!/usr/bin/env python3
"""
Hybrid Orchestrator - uruchamia wszystkie 3 komponenty hybrydowe jako podprocesy:

1. CamoufoxTokenRefresher (Python) - odświeża tokeny co N min
2. CurlCffiPoller (Python) - polling catalog + checkout/build
3. IncogniaConsumeLoop (Node.js) - /v1/consume co 5s

Komunikacja przez hybrid_tokens.json (TokenStore).
"""

import subprocess
import sys
import time
import signal
import os
from pathlib import Path
from typing import Optional, List
import threading
import queue

BASE_DIR = Path(__file__).parent
TOKEN_STORE = BASE_DIR / "hybrid_tokens.json"


class ProcessManager:
    """Zarządza podprocesami z logowaniem i graceful shutdown."""
    
    def __init__(self, name: str, cmd: List[str], cwd: Path = BASE_DIR):
        self.name = name
        self.cmd = cmd
        self.cwd = cwd
        self.proc: Optional[subprocess.Popen] = None
        self.running = False
        self.output_queue = queue.Queue()
        self.reader_thread: Optional[threading.Thread] = None
    
    def start(self) -> bool:
        """Uruchamia podproces."""
        if self.running:
            print(f"[{self.name}] Already running")
            return True
        
        print(f"[{self.name}] Starting: {' '.join(self.cmd)}")
        
        try:
            self.proc = subprocess.Popen(
                self.cmd,
                cwd=self.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1,  # line buffered
            )
            
            self.running = True
            
            # Wątek czytający output
            self.reader_thread = threading.Thread(
                target=self._read_output,
                daemon=True
            )
            self.reader_thread.start()
            
            # Krótkie czekanie na potwierdzenie startu
            time.sleep(0.5)
            
            if self.proc.poll() is not None:
                # Proces już się zakończył (błąd)
                return False
            
            print(f"[{self.name}] ✅ Started (PID: {self.proc.pid})")
            return True
            
        except Exception as e:
            print(f"[{self.name}] ❌ Failed to start: {e}")
            self.running = False
            return False
    
    def _read_output(self):
        """Czyta output podprocesu i loguje z prefiksem."""
        if not self.proc or not self.proc.stdout:
            return
        
        for line in self.proc.stdout:
            line = line.rstrip()
            if line:
                print(f"[{self.name}] {line}")
    
    def stop(self, timeout: float = 10.0) -> bool:
        """Zatrzymuje podproces gracefully."""
        if not self.running or not self.proc:
            return True
        
        print(f"[{self.name}] Stopping...")
        
        try:
            # Najpierw SIGTERM
            if sys.platform == "win32":
                self.proc.terminate()
            else:
                self.proc.send_signal(signal.SIGTERM)
            
            # Czekaj na zakończenie
            try:
                self.proc.wait(timeout=timeout)
                print(f"[{self.name}] ✅ Stopped gracefully")
            except subprocess.TimeoutExpired:
                print(f"[{self.name}] ⚠️ Force killing after {timeout}s")
                self.proc.kill()
                self.proc.wait()
                print(f"[{self.name}] ✅ Force killed")
            
        except Exception as e:
            print(f"[{self.name}] Error stopping: {e}")
        
        self.running = False
        return True
    
    def is_alive(self) -> bool:
        if not self.proc:
            return False
        return self.proc.poll() is None


class HybridOrchestrator:
    """Orkiestrator całego systemu hybrydowego."""
    
    def __init__(self):
        self.processes: List[ProcessManager] = []
        self.shutdown_event = threading.Event()
        
        # Signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        print(f"\n[Orchestrator] Received signal {signum}, initiating shutdown...")
        self.shutdown_event.set()
    
    def add_process(self, name: str, cmd: List[str]) -> ProcessManager:
        pm = ProcessManager(name, cmd)
        self.processes.append(pm)
        return pm
    
    def start_all(self) -> bool:
        """Uruchamia wszystkie procesy w odpowiedniej kolejności."""
        print("=" * 60)
        print("HYBRID ORCHESTRATOR - Starting All Components")
        print("=" * 60)
        
        # 1. Najpierw wyczyść stary token store
        if TOKEN_STORE.exists():
            TOKEN_STORE.unlink()
            print("[Orchestrator] Cleared old token store")
        
        # 2. Uruchom Refresher (musi być pierwszy - dostarcza tokeny)
        refresher = self.add_process(
            "Refresher",
            [sys.executable, "hybrid_camoufox_refresher.py"]
        )
        
        if not refresher.start():
            print("[Orchestrator] ❌ Failed to start Refresher")
            return False
        
        # Daj Refresherowi czas na pierwszy refresh
        print("[Orchestrator] Waiting for Refresher to get initial tokens...")
        time.sleep(5)
        
        # 3. Uruchom Poller
        poller = self.add_process(
            "Poller",
            [sys.executable, "hybrid_curl_cffi_poller.py", "--mode", "poll", "--interval", "30"]
        )
        
        if not poller.start():
            print("[Orchestrator] ❌ Failed to start Poller")
            self.stop_all()
            return False
        
        # 4. Uruchom Consume Loop (Node.js)
        consume = self.add_process(
            "ConsumeLoop",
            ["node", "hybrid_consume_loop.js"]
        )
        
        if not consume.start():
            print("[Orchestrator] ❌ Failed to start ConsumeLoop")
            self.stop_all()
            return False
        
        print("\n" + "=" * 60)
        print("✅ ALL COMPONENTS STARTED SUCCESSFULLY")
        print("=" * 60)
        print("Components running:")
        for p in self.processes:
            print(f"  - {p.name} (PID: {p.proc.pid if p.proc else 'N/A'})")
        print("\nPress Ctrl+C to stop all\n")
        
        return True
    
    def stop_all(self):
        """Zatrzymuje wszystkie procesy w odwrotnej kolejności."""
        print("\n[Orchestrator] Stopping all components...")
        
        # Zatrzymaj w odwrotnej kolejności: ConsumeLoop -> Poller -> Refresher
        for pm in reversed(self.processes):
            pm.stop()
        
        print("[Orchestrator] All components stopped")
    
    def monitor(self):
        """Monitoruje procesy i restartuje jeśli zginęły (opcjonalnie)."""
        print("[Orchestrator] Monitoring started (Ctrl+C to stop)...")
        
        try:
            while not self.shutdown_event.is_set():
                time.sleep(5)
                
                # Sprawdź czy procesy żyją
                dead = []
                for pm in self.processes:
                    if not pm.is_alive():
                        dead.append(pm.name)
                
                if dead:
                    print(f"[Orchestrator] ⚠️ Dead processes: {dead}")
                    # Tutaj można dodać auto-restart
                
        except KeyboardInterrupt:
            pass
    
    def run(self):
        """Główna metoda - start + monitor + shutdown."""
        if not self.start_all():
            self.stop_all()
            return False
        
        try:
            self.monitor()
        finally:
            self.stop_all()
        
        return True


def main():
    print("Vinted Hybrid Bot Orchestrator")
    print("Components:")
    print("  1. CamoufoxTokenRefresher - refreshes Incognia/DataDome tokens")
    print("  2. CurlCffiPoller - polls catalog & executes checkout")
    print("  3. IncogniaConsumeLoop (Node.js) - sends /v1/consume signals")
    print()
    
    orchestrator = HybridOrchestrator()
    success = orchestrator.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()