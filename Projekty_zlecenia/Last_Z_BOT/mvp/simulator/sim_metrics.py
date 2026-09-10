import json
from pathlib import Path
from typing import Any


class SimulationMetricsCollector:
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.iterations: dict[int, dict[str, Any]] = {}

    def record_alert_metrics(
        self,
        iteration: int,
        hit: bool,
        latency_ms: float,
        detection_ms: float,
    ) -> None:
        self.iterations.setdefault(iteration, {})
        self.iterations[iteration].update(
            hit=hit, latency_ms=latency_ms, detection_ms=detection_ms
        )

    def record_reliability(self, iteration: int, recovered: bool) -> None:
        self.iterations.setdefault(iteration, {})
        self.iterations[iteration]["recovered"] = recovered

    def aggregate(self) -> dict[str, Any]:
        total = len(self.iterations)
        if total == 0:
            return {
                "iterations_total": 0,
                "iterations_hit": 0,
                "accuracy_percent": 0.0,
                "latency_avg_ms": None,
                "detection_avg_ms": None,
                "reliability_percent": 0.0,
            }
        hits = sum(1 for it in self.iterations.values() if it.get("hit"))
        lat = [
            it["latency_ms"]
            for it in self.iterations.values()
            if it.get("latency_ms") is not None
        ]
        det = [
            it["detection_ms"]
            for it in self.iterations.values()
            if it.get("detection_ms") is not None
        ]
        recovered = sum(1 for it in self.iterations.values() if it.get("recovered"))
        return {
            "iterations_total": total,
            "iterations_hit": hits,
            "accuracy_percent": (hits / total * 100),
            "latency_avg_ms": (sum(lat) / len(lat)) if lat else None,
            "detection_avg_ms": (sum(det) / len(det)) if det else None,
            "reliability_percent": (recovered / total * 100),
        }

    def export(self, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"session_{self.session_id}.json"
        path.write_text(
            json.dumps(
                {
                    "session_id": self.session_id,
                    "aggregate": self.aggregate(),
                    "iterations": self.iterations,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return path