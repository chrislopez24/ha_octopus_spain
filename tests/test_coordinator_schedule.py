from datetime import datetime
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import types


ROOT = Path(__file__).parents[1]
PACKAGE = types.ModuleType("custom_components.octopus_spain")
PACKAGE.__path__ = [str(ROOT / "custom_components" / "octopus_spain")]
sys.modules.setdefault("custom_components.octopus_spain", PACKAGE)

homeassistant = types.ModuleType("homeassistant")
components = types.ModuleType("homeassistant.components")
http_mod = types.ModuleType("homeassistant.components.http")
http_mod.HomeAssistantView = type("HomeAssistantView", (), {})
config_entries = types.ModuleType("homeassistant.config_entries")
config_entries.ConfigEntry = object
const = types.ModuleType("homeassistant.const")
const.CURRENCY_EURO = "EUR"
const.Platform = types.SimpleNamespace(SENSOR="sensor", BINARY_SENSOR="binary_sensor")
core = types.ModuleType("homeassistant.core")
core.HomeAssistant = object
exceptions = types.ModuleType("homeassistant.exceptions")
exceptions.ConfigEntryAuthFailed = type("ConfigEntryAuthFailed", (Exception,), {})
exceptions.HomeAssistantError = type("HomeAssistantError", (Exception,), {})
helpers = types.ModuleType("homeassistant.helpers")
event = types.ModuleType("homeassistant.helpers.event")
event.async_track_point_in_time = lambda *_args, **_kwargs: None
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

    def __init__(self, hass, *_args, **_kwargs):
        self.hass = hass


update_coordinator.CoordinatorEntity = _FakeCoordinatorEntity
update_coordinator.DataUpdateCoordinator = _FakeDataUpdateCoordinator
update_coordinator.UpdateFailed = type("UpdateFailed", (Exception,), {})

sys.modules.setdefault("homeassistant", homeassistant)
sys.modules.setdefault("homeassistant.components", components)
sys.modules.setdefault("homeassistant.components.http", http_mod)
sys.modules.setdefault("homeassistant.config_entries", config_entries)
sys.modules.setdefault("homeassistant.const", const)
sys.modules.setdefault("homeassistant.core", core)
sys.modules.setdefault("homeassistant.exceptions", exceptions)
sys.modules.setdefault("homeassistant.helpers", helpers)
sys.modules.setdefault("homeassistant.helpers.event", event)
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


def test_next_madrid_hour_aligns_to_next_whole_hour():
    coordinator = load_module("coordinator")

    result = coordinator.next_madrid_hour(datetime.fromisoformat("2026-05-04T13:15:30+02:00"))

    assert result.isoformat() == "2026-05-04T14:00:00+02:00"


def test_next_madrid_hour_moves_forward_when_already_on_boundary():
    coordinator = sys.modules.get("custom_components.octopus_spain.coordinator") or load_module("coordinator")

    result = coordinator.next_madrid_hour(datetime.fromisoformat("2026-05-04T14:00:00+02:00"))

    assert result.isoformat() == "2026-05-04T15:00:00+02:00"
