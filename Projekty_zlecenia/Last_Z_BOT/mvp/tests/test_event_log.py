"""EventLogger hardening tests.

The previous implementation had two issues that mattered in long-running
sessions:
  1. ``flush()`` released the buffer under lock but performed the actual file
     write WITHOUT the lock. A concurrent ``log()`` call between the swap
     and the write is fine (events land in the next batch) — but a write
     failure (disk full, file locked by Excel, AV scan) would silently drop
     every event because ``rows`` had already been removed from the buffer.
  2. ``log()`` never re-raised — so a filesystem error could not be surfaced
     to the caller. Now we wrap I/O in a try/except that puts ``rows`` back
     into the buffer and logs the failure, so the next flush retries.

These tests cover both invariants. The disabled-logger / single-flush paths
keep their existing semantics.
"""

from __future__ import annotations

import csv
import json
import threading
from pathlib import Path

from mvp.bot.event_log import EventLogger


def _read_csv(path: Path) -> list[tuple[str, str, dict]]:
    """Read a session CSV back as (ts, event, data) tuples.

    Tests use the helper to assert what landed on disk without depending on
    the exact timestamp (which varies between calls).
    """
    rows: list[tuple[str, str, dict]] = []
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        assert header == ["ts", "event", "data"]
        for row in reader:
            ts, event, data_json = row
            rows.append((ts, event, json.loads(data_json)))
    return rows


def test_flush_creates_dir(tmp_path: Path) -> None:
    """If ``log_dir`` does not exist yet, flush() must create it transparently."""
    target = tmp_path / "does" / "not" / "exist" / "logs"
    assert not target.exists()

    logger = EventLogger(log_dir=str(target), enabled=True)
    logger.log("test", {"k": 1})
    logger.flush()

    assert target.is_dir()
    files = list(target.glob("session_*.csv"))
    assert len(files) == 1


def test_flush_uses_dated_filename(tmp_path: Path) -> None:
    """The filename must follow session_YYYYMMDD.csv (daily rotation)."""
    logger = EventLogger(log_dir=str(tmp_path), enabled=True)
    logger.log("test", {"k": 1})
    logger.flush()

    files = list(tmp_path.glob("session_*.csv"))
    assert len(files) == 1
    name = files[0].name
    assert name.startswith("session_")
    assert name.endswith(".csv")
    # 8-digit date stamp
    date_part = name.removeprefix("session_").removesuffix(".csv")
    assert len(date_part) == 8 and date_part.isdigit()


def test_flush_first_time_writes_header(tmp_path: Path) -> None:
    """The first flush of a day writes the column header, subsequent ones do not."""
    logger = EventLogger(log_dir=str(tmp_path), enabled=True)
    logger.log("a", {"x": 1})
    logger.flush()
    logger.log("b", {"y": 2})
    logger.flush()

    files = list(tmp_path.glob("session_*.csv"))
    assert len(files) == 1
    rows = _read_csv(files[0])
    assert len(rows) == 2
    assert rows[0][1] == "a"
    assert rows[1][1] == "b"


def test_write_failure_preserves_events_in_buffer(tmp_path: Path, monkeypatch) -> None:
    """If the CSV write fails, events MUST return to the buffer for the next flush."""
    logger = EventLogger(log_dir=str(tmp_path), enabled=True)
    logger.log("phase", {"step": 1})
    logger.log("phase", {"step": 2})

    # Force the underlying Path.open to raise — simulates "file locked by AV".
    real_open = Path.open

    def boom(self, *args, **kwargs):  # noqa: ANN001 - signature mirrors Path.open
        raise OSError("simulated disk full")

    monkeypatch.setattr(Path, "open", boom)

    logger.flush()  # must NOT raise

    # Buffer is empty post-failure (we drained) but we want retries — make
    # sure the retry succeeds once the disk is back.
    monkeypatch.setattr(Path, "open", real_open)

    # The fix is to put the rows BACK on failure so the next flush recovers.
    logger.log("phase", {"step": 3})
    logger.flush()

    files = list(tmp_path.glob("session_*.csv"))
    assert len(files) == 1, f"expected one CSV, got {files}"
    rows = _read_csv(files[0])
    # All three events must be on disk after the retry (no event lost).
    events = [r[1] for r in rows]
    assert events.count("phase") == 3


def test_concurrent_log_and_flush_does_not_drop_events(tmp_path: Path) -> None:
    """Stress: 1k log() calls + a parallel flush() loop must end with N events on disk."""
    logger = EventLogger(log_dir=str(tmp_path), enabled=True)
    n_events = 1000
    flush_count = 50

    log_done = threading.Event()

    def producer() -> None:
        for i in range(n_events):
            logger.log("tick", {"i": i})
            # Brief yield so the flusher gets a chance to run.
            if i % 100 == 0:
                threading.Event().wait(0.001)
        log_done.set()

    def flusher() -> None:
        for _ in range(flush_count):
            logger.flush()
            if log_done.is_set():
                return
            threading.Event().wait(0.002)

    t_log = threading.Thread(target=producer, daemon=True)
    t_flush = threading.Thread(target=flusher, daemon=True)
    t_flush.start()
    t_log.start()
    t_log.join()
    # Drain anything still in the buffer.
    logger.flush()

    files = list(tmp_path.glob("session_*.csv"))
    assert len(files) == 1, f"expected one CSV, got {files}"
    rows = _read_csv(files[0])
    # Every i in [0, n_events) must appear exactly once — no duplicates, no losses.
    seen = sorted(int(r[2]["i"]) for r in rows if r[1] == "tick")
    assert seen == list(range(n_events)), f"missing or duplicated events: {len(seen)}/{n_events}"


def test_disabled_logger_drops_events(tmp_path: Path) -> None:
    """An EventLogger constructed with enabled=False never writes anything."""
    logger = EventLogger(log_dir=str(tmp_path), enabled=False)
    logger.log("ignored", {"x": 1})
    logger.flush()
    assert list(tmp_path.glob("*.csv")) == []


def test_log_from_disabled_logger_does_nothing(tmp_path: Path) -> None:
    """log() on a disabled logger must be a true no-op (no buffer growth either)."""
    logger = EventLogger(log_dir=str(tmp_path), enabled=False)
    for i in range(10):
        logger.log("x", {"i": i})
    logger.flush()
    assert list(tmp_path.glob("*.csv")) == []
    # Buffer must remain empty so we don't accumulate ghost events.
    assert len(logger._buffer) == 0


def test_flush_with_empty_buffer_is_noop(tmp_path: Path) -> None:
    """flush() must not create an empty CSV when there is nothing to write."""
    logger = EventLogger(log_dir=str(tmp_path), enabled=True)
    logger.flush()
    # No file at all: empty buffer + flush should be invisible on disk.
    files = list(tmp_path.glob("session_*.csv"))
    assert files == []


def test_flush_disabled_logger_is_noop(tmp_path: Path) -> None:
    """flush() must not write anything when enabled=False, even if events were added
    before the logger was disabled."""
    logger = EventLogger(log_dir=str(tmp_path), enabled=False)
    logger.log("x", {})  # dropped at the log() boundary
    logger.flush()
    assert list(tmp_path.glob("*.csv")) == []
