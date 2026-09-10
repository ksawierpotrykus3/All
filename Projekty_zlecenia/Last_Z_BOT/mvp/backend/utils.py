from datetime import UTC, datetime


def _coerce_utc(dt: datetime | None) -> datetime | None:
    """Normalize a naive datetime to UTC (SQLite returns datetimes without tzinfo)."""
    if dt is None or dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=UTC)