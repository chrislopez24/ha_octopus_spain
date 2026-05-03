"""Pure helpers shared by Octopus Spain Home Assistant services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
from typing import Any

DEFAULT_HISTORY_DAYS = 31
CLOSED_DATA_DELAY_DAYS = 2
MADRID = ZoneInfo("Europe/Madrid")


@dataclass(frozen=True, slots=True)
class DateRange:
    """Closed date range used by Octopus measurement services."""

    start: date
    end: date


def service_date_range(data: dict[str, Any]) -> DateRange:
    """Return the default closed date range used by services."""

    end = data.get("end_date") or date.today() - timedelta(days=CLOSED_DATA_DELAY_DAYS)
    start = data.get("start_date") or end - timedelta(days=DEFAULT_HISTORY_DAYS)
    return DateRange(start=start, end=end)


def madrid_midnight_range(date_range: DateRange) -> tuple[datetime, datetime]:
    """Return a Madrid-midnight DateTime range for complete daily buckets."""

    return (
        datetime.combine(date_range.start, time.min, MADRID),
        datetime.combine(date_range.end, time.min, MADRID),
    )
