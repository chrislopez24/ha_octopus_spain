import json
from pathlib import Path

from custom_components.octopus_spain import sensor


ROOT = Path(__file__).parents[1]


def test_all_sensor_translation_keys_exist_in_strings_and_spanish_translation():
    keys = {description.translation_key for description in sensor.SENSORS}

    for path in (
        "custom_components/octopus_spain/strings.json",
        "custom_components/octopus_spain/translations/es.json",
    ):
        payload = json.loads((ROOT / path).read_text(encoding="utf-8"))
        assert keys <= payload["entity"]["sensor"].keys()


def test_dashboard_grade_sensor_set_keeps_invoice_opportunistic_and_estimated_costs():
    keys = {description.key for description in sensor.SENSORS}

    assert "last_invoice_amount" in keys
    assert "last_invoice_issued" in keys
    assert "last_complete_day_consumption" in keys
    assert "last_complete_day_estimated_cost" in keys
    assert "week_estimated_cost" in keys
    assert "month_estimated_cost" in keys
    assert "measurement_series" in keys


def test_flat_dashboard_sensors_have_measurement_state_class():
    descriptions = {description.key: description for description in sensor.SENSORS}
    expected = {
        "current_energy_price",
        "last_complete_day_period_total_consumption",
        "last_complete_day_punta_consumption",
        "last_complete_day_llano_consumption",
        "last_complete_day_valle_consumption",
        "current_month_period_total_consumption",
        "current_month_punta_consumption",
        "current_month_llano_consumption",
        "current_month_valle_consumption",
        "current_month_estimated_cost",
        "average_daily_consumption_7d",
        "average_daily_consumption_31d",
        "average_daily_estimated_cost_7d",
        "average_daily_estimated_cost_31d",
    }

    assert expected <= descriptions.keys()
    assert all(descriptions[key].state_class == "measurement" for key in expected)
