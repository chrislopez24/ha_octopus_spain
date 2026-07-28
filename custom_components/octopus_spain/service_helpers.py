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
    """Half-open date range: start is included and end is excluded."""

    start: date
    end: date


def service_date_range(data: dict[str, Any]) -> DateRange:
    """Return a half-open [start_date, end_date) range used by services."""

    end = data.get("end_date") or date.today() - timedelta(days=CLOSED_DATA_DELAY_DAYS)
    start = data.get("start_date") or end - timedelta(days=DEFAULT_HISTORY_DAYS)
    return DateRange(start=start, end=end)


def select_runtime_data(entries: list[Any], data: dict[str, Any]) -> Any:
    """Select one loaded runtime, rejecting an ambiguous service target."""

    loaded = [entry for entry in entries if getattr(entry, "runtime_data", None) is not None]
    entry_id = data.get("config_entry_id")
    if entry_id:
        entry = next((item for item in loaded if item.entry_id == entry_id), None)
        if entry is None:
            raise ValueError("The selected Octopus config entry is not loaded")
        return entry.runtime_data
    if len(loaded) == 1:
        return loaded[0].runtime_data
    if not loaded:
        raise ValueError("Octopus Spain is not configured")
    raise ValueError("config_entry_id is required when multiple Octopus entries are loaded")


def madrid_midnight_range(date_range: DateRange) -> tuple[datetime, datetime]:
    """Return Madrid midnights for the half-open [start, end) range."""

    return (
        datetime.combine(date_range.start, time.min, MADRID),
        datetime.combine(date_range.end, time.min, MADRID),
    )
