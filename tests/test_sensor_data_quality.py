from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import types


ROOT = Path(__file__).parents[1]
PACKAGE = types.ModuleType("custom_components.octopus_spain")
PACKAGE.__path__ = [str(ROOT / "custom_components" / "octopus_spain")]
sys.modules.setdefault("custom_components.octopus_spain", PACKAGE)


def load_module(name: str):
    spec = spec_from_file_location(
        f"custom_components.octopus_spain.{name}",
        ROOT / "custom_components" / "octopus_spain" / f"{name}.py",
    )
    assert spec and spec.loader
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


measurements = load_module("measurements")
mappers = load_module("mappers")


def test_daily_rollups_ignore_partial_days_when_requested():
    points = [
        {
            "start_at": "2026-04-01T16:00:00+02:00",
            "end_at": "2026-04-02T00:00:00+02:00",
            "value": 99,
            "unit": "kwh",
            "cost_incl_tax": None,
        },
        {
            "start_at": "2026-04-02T00:00:00+02:00",
            "end_at": "2026-04-03T00:00:00+02:00",
            "value": 10,
            "unit": "kwh",
            "cost_incl_tax": None,
        },
    ]

    result = measurements.measurement_rollups(points, complete_daily_only=True)

    assert result["points_count"] == 1
    assert result["last_day_consumption_kwh"] == 10.0
    assert result["latest_period_start"] == "2026-04-02T00:00:00+02:00"
    assert result["latest_period_end"] == "2026-04-03T00:00:00+02:00"


def test_estimated_sun_club_costs_are_derived_from_hourly_consumption():
    daily_points = [
        {
            "start_at": "2026-04-01T00:00:00+02:00",
            "end_at": "2026-04-02T00:00:00+02:00",
            "value": 3,
            "unit": "kwh",
            "cost_incl_tax": None,
        }
    ]
    hourly_points = [
        {
            "start_at": "2026-04-01T11:00:00+02:00",
            "end_at": "2026-04-01T12:00:00+02:00",
            "value": 1,
            "unit": "kwh",
            "cost_incl_tax": None,
        },
        {
            "start_at": "2026-04-01T12:00:00+02:00",
            "end_at": "2026-04-01T13:00:00+02:00",
            "value": 2,
            "unit": "kwh",
            "cost_incl_tax": None,
        },
    ]

    result = measurements.estimated_energy_costs_from_hourly(
        daily_points,
        hourly_points,
        base_energy_price=0.13,
        sun_club_discount=0.45,
        sun_club_start_hour=12,
        sun_club_end_hour=18,
    )

    assert result["estimated_last_day_cost_eur"] == 0.273
    assert result["estimated_last_7_days_cost_eur"] == 0.273
    assert result["estimated_last_31_days_cost_eur"] == 0.273
    assert result["estimated_cost_days_count"] == 1
    assert result["estimated_cost_source"] == "estimated_from_hourly_consumption_and_tariff"
    assert result["series_by_date"] == {"2026-04-01": 0.273}


def test_hourly_measurement_totals_keep_hourly_points_for_services():
    points = [
        {"start_at": "2026-04-01T10:00:00+02:00", "end_at": "2026-04-01T11:00:00+02:00", "value": 2, "unit": "kwh"},
        {"start_at": "2026-04-01T14:00:00+02:00", "end_at": "2026-04-01T15:00:00+02:00", "value": 3, "unit": "kwh"},
    ]

    result = mappers.measurement_totals(points)

    assert result["points_count"] == 2
    assert result["total_consumption_kwh"] == 5.0
    assert result["last_day_consumption_kwh"] == 5.0


def test_hourly_chart_series_are_bucketed_for_dashboard_bars():
    points = [
        {"start_at": "2026-04-01T00:00:00+02:00", "end_at": "2026-04-01T01:00:00+02:00", "value": 1, "unit": "kwh"},
        {"start_at": "2026-04-01T10:00:00+02:00", "end_at": "2026-04-01T11:00:00+02:00", "value": 2, "unit": "kwh"},
        {"start_at": "2026-04-01T14:00:00+02:00", "end_at": "2026-04-01T15:00:00+02:00", "value": 3, "unit": "kwh"},
        {"start_at": "2026-05-01T14:00:00+02:00", "end_at": "2026-05-01T15:00:00+02:00", "value": 4, "unit": "kwh"},
    ]

    result = measurements.measurement_period_series(points)

    assert result["daily"] == [
        {"date": "2026-04-01", "total_kwh": 6.0, "punta_kwh": 2.0, "llano_kwh": 3.0, "valle_kwh": 1.0},
        {"date": "2026-05-01", "total_kwh": 4.0, "punta_kwh": 0.0, "llano_kwh": 4.0, "valle_kwh": 0.0},
    ]
    assert result["monthly"] == [
        {"period": "2026-04", "total_kwh": 6.0, "punta_kwh": 2.0, "llano_kwh": 3.0, "valle_kwh": 1.0},
        {"period": "2026-05", "total_kwh": 4.0, "punta_kwh": 0.0, "llano_kwh": 4.0, "valle_kwh": 0.0},
    ]


def test_credit_amounts_are_exposed_in_euros_not_minor_units():
    payload = {
        "data": {
            "account": {
                "ledgers": [
                    {
                        "transactions": {
                            "edges": [
                                {
                                    "node": {
                                        "__typename": "Credit",
                                        "reasonCode": "SUN_CLUB",
                                        "amounts": {"gross": 999},
                                        "createdAt": "2026-04-08T00:00:00+02:00",
                                    }
                                },
                                {
                                    "node": {
                                        "__typename": "Credit",
                                        "reasonCode": "SUN_CLUB",
                                        "amounts": {"gross": 1140},
                                        "createdAt": "2026-03-09T00:00:00+02:00",
                                    }
                                },
                            ]
                        }
                    }
                ]
            }
        }
    }

    result = mappers.summarize_credits(payload)

    assert result["reason_code_amounts"] == {"SUN_CLUB": 21.39}
    assert result["recent_credits"][0]["amount"] == 9.99
