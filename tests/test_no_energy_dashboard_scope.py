import json
from pathlib import Path


ROOT = Path(__file__).parents[1]


def _json(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_manifest_has_no_storage_integration_dependency():
    manifest = _json("custom_components/octopus_spain/manifest.json")
    forbidden_dependency = "rec" + "order"

    assert forbidden_dependency not in manifest.get("after_dependencies", [])


def test_services_expose_only_api_response_helpers():
    services_py = (ROOT / "custom_components/octopus_spain/services.py").read_text(encoding="utf-8")
    services_yaml = (ROOT / "custom_components/octopus_spain/services.yaml").read_text(encoding="utf-8")
    forbidden_action = "import" + "_" + "statistics"
    forbidden_helper = "async" + "_" + "import" + "_" + "measurement" + "_" + "statistics"

    assert forbidden_action not in services_py
    assert forbidden_helper not in services_py
    assert f"{forbidden_action}:" not in services_yaml


def test_translations_cover_graph_series_sensors_without_storage_service():
    expected_sensor_keys = {
        "week_consumption",
        "week_estimated_cost",
        "month_consumption",
        "month_estimated_cost",
        "last_complete_day_consumption",
        "last_complete_day_estimated_cost",
        "measurement_series",
    }

    for path in (
        "custom_components/octopus_spain/strings.json",
        "custom_components/octopus_spain/translations/es.json",
    ):
        payload = _json(path)
        sensors = payload["entity"]["sensor"]
        assert expected_sensor_keys <= sensors.keys()
        forbidden_action = "import" + "_" + "statistics"
        forbidden_exception = "statistics" + "_" + "import" + "_" + "failed"
        assert forbidden_action not in payload.get("services", {})
        assert forbidden_exception not in payload.get("exceptions", {})
