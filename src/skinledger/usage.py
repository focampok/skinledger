"""API usage accounting and unit caps per Guatemala day and in total."""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    GUATEMALA_TZ = ZoneInfo("America/Guatemala")
except ZoneInfoNotFoundError:  # pragma: no cover - minimal images without tzdata
    # Guatemala has used UTC-6 without daylight saving since 2006.
    GUATEMALA_TZ = timezone(timedelta(hours=-6), "America/Guatemala")


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc_now_iso() -> str:
    """UTC timestamp in the same shape as SQLite's strftime('%Y-%m-%dT%H:%M:%fZ')."""
    return utc_now().isoformat(timespec="milliseconds").replace("+00:00", "Z")


def guatemala_day(now: datetime | None = None) -> date:
    """Calendar day in America/Guatemala; never the UTC day."""
    if now is None:
        now = utc_now()
    elif now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return now.astimezone(GUATEMALA_TZ).date()


def guatemala_today(now: datetime | None = None) -> str:
    return guatemala_day(now).isoformat()


def projected_units(stored_units: int | None, units_per_analysis: int) -> int:
    """Units an api_usage row reserves. Mock rows store 0 but still hold a slot."""
    return stored_units if stored_units else units_per_analysis


def visitor_units_for_day(
    conn: sqlite3.Connection, day: str, units_per_analysis: int
) -> int:
    rows = conn.execute(
        "SELECT units FROM api_usage WHERE day = ? AND is_admin = 0", (day,)
    )
    return sum(projected_units(row["units"], units_per_analysis) for row in rows)


def visitor_units_total(conn: sqlite3.Connection, units_per_analysis: int) -> int:
    rows = conn.execute("SELECT units FROM api_usage WHERE is_admin = 0")
    return sum(projected_units(row["units"], units_per_analysis) for row in rows)
