# coding: utf-8
"""Seria benchmarku curl_cffi -> bramka: 3 przebiegi, kazdy na swiezym itemie.

Zbiera czasy do bramki (payment pending) i liczy percentyle. Kazdy przebieg
zapisuje screenshot bramki z wypalonym znacznikiem czasu (dowod wizualny).
"""
import json
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
N_RUNS = 3


def _percentile(vals, pct):
    if not vals:
        return 0.0
    s = sorted(vals)
    idx = min(len(s) - 1, int(pct / 100 * len(s)))
    return round(s[idx], 1)


def main():
    runs = []
    for i in range(1, N_RUNS + 1):
        print(f"\n===== PRZEBIEG {i}/{N_RUNS} =====", flush=True)
        # import i uruchomienie swieze (osobny proces -> swiezy T0)
        import subprocess, sys
        r = subprocess.run([sys.executable, str(BASE_DIR / "bench_curl_gateway.py")],
                           capture_output=True, text=True, cwd=str(BASE_DIR), timeout=180)
        out = (r.stdout or "") + (r.stderr or "")
        print(out[-1500:], flush=True)
        w = json.loads((BASE_DIR / "bench_gateway_wynik.json").read_text(encoding="utf-8"))
        # przemianuj artefakty per run (usun stare, zeby uniknac kolizji)
        for name in ("bench_gateway_bramka.png", "bench_gateway_bramka_dowod.png",
                      "bench_gateway_wynik.json"):
            src = BASE_DIR / name
            dst = BASE_DIR / f"bench_gateway_run{i}_{name.split('bench_gateway_',1)[1]}"
            if src.exists():
                if dst.exists():
                    dst.unlink()
                src.rename(dst)
        runs.append({"run": i, "to_gateway_ms": w["elapsed"].get("to_gateway_ms"),
                     "success": w.get("success"),
                     "item": w.get("item", {}).get("id"),
                     "txn": w.get("txn", {}).get("id"),
                     "payment_status": (w.get("steps") or [{}])[-3].get("payment_status")
                     if len(w.get("steps", [])) >= 3 else None})
        time.sleep(3)  # odstep miedzy przebiegami

    gw = [r["to_gateway_ms"] for r in runs if r.get("to_gateway_ms")]
    summary = {
        "runs": runs,
        "to_gateway_ms": {
            "samples": gw,
            "p50": _percentile(gw, 50),
            "p95": _percentile(gw, 95),
            "min": min(gw) if gw else None,
            "max": max(gw) if gw else None,
        },
    }
    (BASE_DIR / "bench_gateway_seria.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n===== PODSUMOWANIE =====")
    print(json.dumps(summary["to_gateway_ms"], indent=2), flush=True)
    print("Zapisano: bench_gateway_seria.json", flush=True)


if __name__ == "__main__":
    main()
