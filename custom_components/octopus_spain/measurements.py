"""Graph-friendly measurement helpers for Octopus Energy Spain."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable


@dataclass(frozen=True, slots=True)
class MeasurementPoint:
    """Normalized safe measurement point."""

    start: datetime
    end: datetime | None
    kwh: float
    cost_eur: float | None


def measurement_rollups(
    points: list[dict[str, Any]], *, complete_daily_only: bool = False, bucket_same_day: bool = False
) -> dict[str, Any]:
    """Return common rolling totals used by sensors and dashboards."""

    normalized = normalize_measurement_points(points, complete_daily_only=complete_daily_only)
    last_day_points = _points_on_latest_date(normalized) if bucket_same_day else normalized[-1:]
    return {
        "last_day_consumption_kwh": _sum_kwh(last_day_points),
        "last_day_cost_eur": _sum_cost(last_day_points),
        "last_7_days_consumption_kwh": _sum_kwh(_points_in_last_days(normalized, 7)),
        "last_7_days_cost_eur": _sum_cost(_points_in_last_days(normalized, 7)),
        "last_31_days_consumption_kwh": _sum_kwh(_points_in_last_days(normalized, 31)),
        "last_31_days_cost_eur": _sum_cost(_points_in_last_days(normalized, 31)),
        "last_365_days_consumption_kwh": _sum_kwh(_points_in_last_days(normalized, 365)),
        "last_365_days_cost_eur": _sum_cost(_points_in_last_days(normalized, 365)),
        "latest_period_start": normalized[-1].start.isoformat() if normalized else None,
        "latest_period_end": normalized[-1].end.isoformat() if normalized and normalized[-1].end else None,
        "points_count": len(normalized),
        "complete_daily_only": complete_daily_only,
    }


def measurement_graph_series(
    points: list[dict[str, Any]], *, complete_daily_only: bool = False
) -> dict[str, list[dict[str, Any]]]:
    """Return daily/weekly/monthly/yearly series suitable for graph cards."""

    normalized = normalize_measurement_points(points, complete_daily_only=complete_daily_only)
    return {
        "daily": _daily_series(normalized),
        "weekly": _bucket_series(normalized, _week_key),
        "monthly": _bucket_series(normalized, lambda point: point.start.strftime("%Y-%m")),
        "yearly": _bucket_series(normalized, lambda point: point.start.strftime("%Y")),
    }


def measurement_period_series(points: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Return daily/monthly kWh split into Spanish 2.0TD-like periods for bar charts."""

    normalized = normalize_measurement_points(points)
    return {
        "daily": _period_bucket_series(normalized, lambda point: point.start.date().isoformat(), "date"),
        "monthly": _period_bucket_series(normalized, lambda point: point.start.strftime("%Y-%m"), "period"),
    }


def estimated_energy_costs_from_hourly(
    daily_points: list[dict[str, Any]],
    hourly_points: list[dict[str, Any]],
    *,
    base_energy_price: float | None,
    sun_club_discount: float,
    sun_club_start_hour: int,
    sun_club_end_hour: int,
) -> dict[str, Any]:
    """Estimate energy-only costs from hourly kWh and the current Sun Club tariff."""

    if base_energy_price is None:
        return _empty_estimated_costs("unavailable")
    daily_dates = {point.start.date().isoformat() for point in normalize_measurement_points(daily_points, complete_daily_only=True)}
    costs_by_date = _estimated_costs_by_date(
        normalize_measurement_points(hourly_points),
        daily_dates,
        base_energy_price,
        sun_club_discount,
        sun_club_start_hour,
        sun_club_end_hour,
    )
    cost_points = [_cost_point(date, cost) for date, cost in costs_by_date.items()]
    rollups = _estimated_cost_rollups(cost_points)
    return {
        **rollups,
        "estimated_cost_source": "estimated_from_hourly_consumption_and_tariff" if costs_by_date else "unavailable",
        "estimated_cost_days_count": len(costs_by_date),
        "estimated_cost_includes_power": False,
        "estimated_cost_includes_taxes": False,
        "series_by_date": costs_by_date,
    }


def normalize_measurement_points(
    points: list[dict[str, Any]], *, complete_daily_only: bool = False
) -> list[MeasurementPoint]:
    """Normalize raw mapper points and drop invalid/sensitive fields."""

    normalized: list[MeasurementPoint] = []
    for point in points:
        parsed = _normalized_point(point)
        if parsed is None or (complete_daily_only and not _is_complete_daily_point(parsed)):
            continue
        normalized.append(parsed)
    return sorted(normalized, key=lambda item: item.start)


def _normalized_point(point: dict[str, Any]) -> MeasurementPoint | None:
    start = _parse_datetime(point.get("start_at"))
    end = _parse_datetime(point.get("end_at"))
    kwh = _float_or_none(point.get("value"))
    unit = str(point.get("unit") or "").lower()
    if start is None or kwh is None or kwh < 0 or unit != "kwh":
        return None
    cost = _float_or_none(point.get("cost_incl_tax"))
    if cost is not None and cost < 0:
        cost = None
    return MeasurementPoint(start=start, end=end, kwh=kwh, cost_eur=cost)


def _daily_series(points: list[MeasurementPoint]) -> list[dict[str, Any]]:
    return [
        {"date": point.start.date().isoformat(), "kwh": round(point.kwh, 6), "cost_eur": _round_or_none(point.cost_eur)}
        for point in points
    ]


def _period_bucket_series(
    points: list[MeasurementPoint], key_fn: Callable[[MeasurementPoint], str], key_name: str
) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, float]] = {}
    for point in points:
        key = key_fn(point)
        bucket = buckets.setdefault(key, {"punta_kwh": 0.0, "llano_kwh": 0.0, "valle_kwh": 0.0})
        bucket[f"{_spanish_period(point.start)}_kwh"] += point.kwh
    return [_period_row(key_name, key, bucket) for key, bucket in sorted(buckets.items())]


def _period_row(key_name: str, key: str, bucket: dict[str, float]) -> dict[str, Any]:
    punta = round(bucket["punta_kwh"], 6)
    llano = round(bucket["llano_kwh"], 6)
    valle = round(bucket["valle_kwh"], 6)
    return {key_name: key, "total_kwh": round(punta + llano + valle, 6), "punta_kwh": punta, "llano_kwh": llano, "valle_kwh": valle}


def _spanish_period(value: datetime) -> str:
    if value.weekday() >= 5:
        return "valle"
    if 10 <= value.hour < 14 or 18 <= value.hour < 22:
        return "punta"
    if 8 <= value.hour < 10 or 14 <= value.hour < 18 or 22 <= value.hour < 24:
        return "llano"
    return "valle"


def _estimated_costs_by_date(
    points: list[MeasurementPoint],
    daily_dates: set[str],
    base_price: float,
    discount: float,
    start_hour: int,
    end_hour: int,
) -> dict[str, float]:
    costs: dict[str, float] = {}
    for point in points:
        key = point.start.date().isoformat()
        if key not in daily_dates:
            continue
        price = base_price * (1 - discount) if start_hour <= point.start.hour < end_hour else base_price
        costs[key] = costs.get(key, 0.0) + point.kwh * price
    return {key: round(value, 6) for key, value in sorted(costs.items())}


def _cost_point(date_key: str, cost: float) -> MeasurementPoint:
    start = datetime.fromisoformat(f"{date_key}T00:00:00+00:00")
    return MeasurementPoint(start=start, end=start + timedelta(days=1), kwh=0.0, cost_eur=cost)


def _estimated_cost_rollups(points: list[MeasurementPoint]) -> dict[str, float | None]:
    return {
        "estimated_last_day_cost_eur": _sum_cost(points[-1:]),
        "estimated_last_7_days_cost_eur": _sum_cost(_points_in_last_days(points, 7)),
        "estimated_last_31_days_cost_eur": _sum_cost(_points_in_last_days(points, 31)),
        "estimated_last_365_days_cost_eur": _sum_cost(_points_in_last_days(points, 365)),
    }


def _empty_estimated_costs(source: str) -> dict[str, Any]:
    return {
        "estimated_last_day_cost_eur": None,
        "estimated_last_7_days_cost_eur": None,
        "estimated_last_31_days_cost_eur": None,
        "estimated_last_365_days_cost_eur": None,
        "estimated_cost_source": source,
        "estimated_cost_days_count": 0,
        "estimated_cost_includes_power": False,
        "estimated_cost_includes_taxes": False,
        "series_by_date": {},
    }


def _is_complete_daily_point(point: MeasurementPoint) -> bool:
    if point.end is None:
        return False
    return (
        point.start.hour == point.start.minute == point.start.second == point.start.microsecond == 0
        and point.end.hour == point.end.minute == point.end.second == point.end.microsecond == 0
        and (point.end.date() - point.start.date()).days == 1
    )


def _points_on_latest_date(points: list[MeasurementPoint]) -> list[MeasurementPoint]:
    if not points:
        return []
    latest = points[-1].start.date()
    return [point for point in points if point.start.date() == latest]


def _points_in_last_days(points: list[MeasurementPoint], days: int) -> list[MeasurementPoint]:
    if not points:
        return []
    first_date = points[-1].start.date().toordinal() - days + 1
    return [point for point in points if point.start.date().toordinal() >= first_date]


def _bucket_series(points: list[MeasurementPoint], key_fn: Callable[[MeasurementPoint], str]) -> list[dict[str, Any]]:
    buckets: dict[str, list[MeasurementPoint]] = {}
    for point in points:
        buckets.setdefault(key_fn(point), []).append(point)
    return [
        {"period": period, "kwh": _sum_kwh(bucket_points), "cost_eur": _sum_cost(bucket_points)}
        for period, bucket_points in sorted(buckets.items())
    ]


def _week_key(point: MeasurementPoint) -> str:
    year, week, _weekday = point.start.isocalendar()
    return f"{year}-W{week:02d}"


def _sum_kwh(points: Iterable[MeasurementPoint]) -> float | None:
    values = list(points)
    if not values:
        return None
    return round(sum(point.kwh for point in values), 6)


def _sum_cost(points: Iterable[MeasurementPoint]) -> float | None:
    values = [point.cost_eur for point in points if point.cost_eur is not None]
    if not values:
        return None
    return round(sum(values), 6)


def _round_or_none(value: float | None) -> float | None:
    return round(value, 6) if value is not None else None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
