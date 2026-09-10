"""Repozytorium pomiarowe: rejestratory latencji i timer checkoutu. Czyste, bez I/O."""
import time
from dataclasses import dataclass, field


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = min(len(s) - 1, int(pct / 100 * len(s)))
    return round(s[idx], 3)


@dataclass
class LatencyRecorder:
    """Zbiera próbki latencji i liczy percentyle."""

    samples: list[float] = field(default_factory=list)
    errors: int = 0

    @property
    def count(self) -> int:
        return len(self.samples)

    @property
    def p50(self) -> float:
        return _percentile(self.samples, 50)

    @property
    def p95(self) -> float:
        return _percentile(self.samples, 95)

    @property
    def p99(self) -> float:
        return _percentile(self.samples, 99)

    @property
    def avg(self) -> float:
        if not self.samples:
            return 0.0
        return round(sum(self.samples) / len(self.samples), 3)

    def add(self, value_ms: float) -> None:
        self.samples.append(value_ms)

    def record_error(self) -> None:
        self.errors += 1

    def to_dict(self) -> dict:
        return {
            "count": self.count,
            "errors": self.errors,
            "p50": self.p50,
            "p95": self.p95,
            "p99": self.p99,
            "avg": self.avg,
        }


class StepTimings(dict):
    """Rejestruje czas kroków checkoutu (ms)."""

    @property
    def suma(self) -> float:
        return round(sum(v for v in self.values() if isinstance(v, (int, float))), 3)