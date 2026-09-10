"""Helpers shared by the cloud provider tools."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def today_utc() -> date:
    """Today's date in UTC."""
    return datetime.now(timezone.utc).date()


def clamp(value: int, low: int, high: int) -> int:
    """Clamp an integer into ``[low, high]``."""
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = low
    return max(low, min(value, high))


def _shift_months(day: date, months_back: int) -> date:
    """First day of the month ``months_back`` months before ``day``'s month."""
    year = day.year
    month = day.month - months_back
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


def month_range(months: int) -> tuple[str, str]:
    """Return an ISO ``(start, end)`` covering the current month plus ``months - 1`` prior months.

    ``end`` is today (exclusive for AWS Cost Explorer). When today is the first
    of the month the range is pushed back one month so it is never empty.
    """
    months = clamp(months, 1, 12)
    end = today_utc()
    start = _shift_months(end, months - 1)
    if start >= end:
        start = _shift_months(end, months)
    return start.isoformat(), end.isoformat()


def day_range(days: int, max_days: int = 365) -> tuple[str, str]:
    """Return an ISO ``(start, end)`` for the last ``days`` days ending today."""
    days = clamp(days, 1, max_days)
    end = today_utc()
    start = end - timedelta(days=days)
    return start.isoformat(), end.isoformat()


def parse_date_range(
    start_date: str | None, end_date: str | None, default_days: int = 30
) -> tuple[str, str]:
    """Validate optional ``YYYY-MM-DD`` bounds, defaulting to the last ``default_days`` days.

    Raises:
        ValueError: If a supplied date is malformed or the range is inverted.
    """
    default_start, default_end = day_range(default_days)
    start = (start_date or "").strip() or default_start
    end = (end_date or "").strip() or default_end
    for label, value in (("start_date", start), ("end_date", end)):
        if not _DATE_RE.match(value):
            raise ValueError(f"{label} must be in YYYY-MM-DD format, got {value!r}")
        date.fromisoformat(value)  # raises for impossible dates
    if start >= end:
        raise ValueError("start_date must be earlier than end_date")
    return start, end


def error_result(provider: str, message: str, **extra: Any) -> dict[str, Any]:
    """Standard error payload returned to the model."""
    payload: dict[str, Any] = {"provider": provider, "error": message}
    payload.update(extra)
    return payload


def round_money(value: Any) -> float:
    """Round a cost to cents, tolerating strings and ``None``."""
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0
