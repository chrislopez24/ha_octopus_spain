from dataclasses import dataclass
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys
import types


ROOT = Path(__file__).parents[1]
PACKAGE = types.ModuleType("custom_components.octopus_spain")
PACKAGE.__path__ = [str(ROOT / "custom_components" / "octopus_spain")]
sys.modules.setdefault("custom_components.octopus_spain", PACKAGE)


class _FakeSensorDeviceClass:
    DATE = "date"
    ENERGY = "energy"
    MONETARY = "monetary"


class _FakeSensorEntity:
    pass


@dataclass(frozen=True, kw_only=True)
class _FakeSensorEntityDescription:
    key: str | None = None
    translation_key: str | None = None
    device_class: str | None = None
    native_unit_of_measurement: str | None = None
    suggested_display_precision: int | None = None


homeassistant = types.ModuleType("homeassistant")
components = types.ModuleType("homeassistant.components")
sensor_mod = types.ModuleType("homeassistant.components.sensor")
sensor_mod.SensorDeviceClass = _FakeSensorDeviceClass
sensor_mod.SensorEntity = _FakeSensorEntity
sensor_mod.SensorEntityDescription = _FakeSensorEntityDescription
config_entries = types.ModuleType("homeassistant.config_entries")
config_entries.ConfigEntry = object
const = types.ModuleType("homeassistant.const")
const.CURRENCY_EURO = "EUR"
const.Platform = types.SimpleNamespace(SENSOR="sensor", BINARY_SENSOR="binary_sensor")
core = types.ModuleType("homeassistant.core")
core.HomeAssistant = object
exceptions = types.ModuleType("homeassistant.exceptions")
exceptions.ConfigEntryAuthFailed = type("ConfigEntryAuthFailed", (Exception,), {})
helpers = types.ModuleType("homeassistant.helpers")
entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
entity_platform.AddEntitiesCallback = object
device_registry = types.ModuleType("homeassistant.helpers.device_registry")
device_registry.DeviceInfo = dict
update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")


class _FakeCoordinatorEntity:
    @classmethod
    def __class_getitem__(cls, _item):
        return cls

    def __init__(self, *_args, **_kwargs):
        pass


class _FakeDataUpdateCoordinator:
    @classmethod
    def __class_getitem__(cls, _item):
        return cls

    def __init__(self, *_args, **_kwargs):
        pass


update_coordinator.CoordinatorEntity = _FakeCoordinatorEntity
update_coordinator.DataUpdateCoordinator = _FakeDataUpdateCoordinator
update_coordinator.UpdateFailed = type("UpdateFailed", (Exception,), {})

sys.modules.setdefault("homeassistant", homeassistant)
sys.modules.setdefault("homeassistant.components", components)
sys.modules.setdefault("homeassistant.components.sensor", sensor_mod)
sys.modules.setdefault("homeassistant.config_entries", config_entries)
sys.modules.setdefault("homeassistant.const", const)
sys.modules.setdefault("homeassistant.core", core)
sys.modules.setdefault("homeassistant.exceptions", exceptions)
sys.modules.setdefault("homeassistant.helpers", helpers)
sys.modules.setdefault("homeassistant.helpers.entity_platform", entity_platform)
sys.modules.setdefault("homeassistant.helpers.device_registry", device_registry)
sys.modules.setdefault("homeassistant.helpers.update_coordinator", update_coordinator)


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


def test_all_sensor_translation_keys_exist_in_strings_and_spanish_translation():
    load_module("const")
    load_module("model")
    load_module("entity")
    load_module("coordinator")
    sensor = load_module("sensor")
    keys = {description.translation_key for description in sensor.SENSORS}

    for path in (
        "custom_components/octopus_spain/strings.json",
        "custom_components/octopus_spain/translations/es.json",
    ):
        payload = json.loads((ROOT / path).read_text(encoding="utf-8"))
        assert keys <= payload["entity"]["sensor"].keys()


def test_dashboard_grade_sensor_set_keeps_invoice_opportunistic_and_estimated_costs():
    sensor = sys.modules.get("custom_components.octopus_spain.sensor") or load_module("sensor")
    keys = {description.key for description in sensor.SENSORS}

    assert "last_invoice_amount" in keys
    assert "last_invoice_issued" in keys
    assert "last_complete_day_consumption" in keys
    assert "last_complete_day_estimated_cost" in keys
    assert "week_estimated_cost" in keys
    assert "month_estimated_cost" in keys
    assert "measurement_series" in keys
