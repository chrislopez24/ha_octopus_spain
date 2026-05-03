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


def test_measurement_rollups_return_day_week_month_year_totals():
    points = [
        {"start_at": "2026-01-01T00:00:00+01:00", "value": 1, "unit": "kwh", "cost_incl_tax": 0.2},
        {"start_at": "2026-01-02T00:00:00+01:00", "value": 2, "unit": "kwh", "cost_incl_tax": None},
        {"start_at": "2026-01-08T00:00:00+01:00", "value": 4, "unit": "kwh", "cost_incl_tax": 0.8},
    ]

    result = measurements.measurement_rollups(points)

    assert result["last_day_consumption_kwh"] == 4.0
    assert result["last_day_cost_eur"] == 0.8
    assert result["last_7_days_consumption_kwh"] == 6.0
    assert result["last_7_days_cost_eur"] == 0.8
    assert result["last_31_days_consumption_kwh"] == 7.0
    assert result["last_365_days_consumption_kwh"] == 7.0


def test_measurement_series_are_redacted_graph_friendly_and_bucketed():
    points = [
        {"start_at": "2026-01-01T00:00:00+01:00", "value": 1, "unit": "kwh", "cost_incl_tax": 0.2},
        {"start_at": "2026-01-02T00:00:00+01:00", "value": 2, "unit": "kwh", "cost_incl_tax": 0.3},
        {"start_at": "2026-02-01T00:00:00+01:00", "value": 4, "unit": "kwh", "cost_incl_tax": None},
    ]

    result = measurements.measurement_graph_series(points)

    assert result["daily"][0] == {"date": "2026-01-01", "kwh": 1.0, "cost_eur": 0.2}
    assert result["weekly"][0]["period"].startswith("2026-W")
    assert result["weekly"][0]["kwh"] == 3.0
    assert result["monthly"] == [
        {"period": "2026-01", "kwh": 3.0, "cost_eur": 0.5},
        {"period": "2026-02", "kwh": 4.0, "cost_eur": None},
    ]


def test_measurement_helpers_skip_invalid_non_kwh_and_negative_points():
    points = [
        {"start_at": "2026-01-01T00:00:00+01:00", "value": 1, "unit": "kwh", "cost_incl_tax": 0.2},
        {"start_at": "2026-01-02T00:00:00+01:00", "value": -2, "unit": "kwh", "cost_incl_tax": 0.3},
        {"start_at": "2026-01-03T00:00:00+01:00", "value": 3, "unit": "m3", "cost_incl_tax": 0.4},
        {"start_at": None, "value": 4, "unit": "kwh", "cost_incl_tax": 0.5},
    ]

    result = measurements.measurement_graph_series(points)

    assert result["daily"] == [{"date": "2026-01-01", "kwh": 1.0, "cost_eur": 0.2}]
