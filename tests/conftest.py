from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
import types

ROOT = Path(__file__).parents[1]

package = types.ModuleType("custom_components.octopus_spain")
package.__path__ = [str(ROOT / "custom_components" / "octopus_spain")]
sys.modules.setdefault("custom_components.octopus_spain", package)


class _FakeHomeAssistantView:
    pass


class _FakeSensorDeviceClass:
    DATE = "date"
    ENERGY = "energy"
    MONETARY = "monetary"


class _FakeSensorStateClass:
    MEASUREMENT = "measurement"


class _FakeSensorEntity:
    pass


class _FakeBinarySensorEntity:
    pass


@dataclass(frozen=True, kw_only=True)
class _FakeSensorEntityDescription:
    key: str | None = None
    translation_key: str | None = None
    icon: str | None = None
    device_class: str | None = None
    native_unit_of_measurement: str | None = None
    suggested_display_precision: int | None = None
    state_class: str | None = None


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

    def __init__(self, hass=None, *_args, **_kwargs):
        self.hass = hass


def _module(name: str, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules.setdefault(name, module)
    return module


_module(
    "custom_components.octopus_spain.services",
    first_runtime_data=lambda _hass: None,
    runtime_data_for_invoice_hash=lambda _hass, _invoice_id_hash: None,
)
_module("homeassistant")
_module("homeassistant.components")
_module(
    "homeassistant.components.binary_sensor",
    BinarySensorEntity=_FakeBinarySensorEntity,
    BinarySensorEntityDescription=_FakeSensorEntityDescription,
)
_module("homeassistant.components.http", HomeAssistantView=_FakeHomeAssistantView, StaticPathConfig=object)
_module(
    "homeassistant.components.sensor",
    SensorDeviceClass=_FakeSensorDeviceClass,
    SensorEntity=_FakeSensorEntity,
    SensorEntityDescription=_FakeSensorEntityDescription,
    SensorStateClass=_FakeSensorStateClass,
)
_module("homeassistant.config_entries", ConfigEntry=object)
_module("homeassistant.const", CURRENCY_EURO="EUR", Platform=types.SimpleNamespace(SENSOR="sensor", BINARY_SENSOR="binary_sensor"))
_module("homeassistant.core", HomeAssistant=object, ServiceCall=object, ServiceResponse=dict, SupportsResponse=types.SimpleNamespace(ONLY="only"))
_module(
    "homeassistant.exceptions",
    ConfigEntryAuthFailed=type("ConfigEntryAuthFailed", (Exception,), {}),
    HomeAssistantError=type("HomeAssistantError", (Exception,), {}),
    ServiceValidationError=type("ServiceValidationError", (Exception,), {}),
)
_module("homeassistant.helpers")
_module("homeassistant.helpers.config_validation", string=str, date=lambda value: value)
_module("homeassistant.helpers.device_registry", DeviceInfo=dict)
_module("homeassistant.helpers.entity_platform", AddEntitiesCallback=object)
_module("homeassistant.helpers.event", async_track_point_in_time=lambda *_args, **_kwargs: None)
_module(
    "homeassistant.helpers.update_coordinator",
    CoordinatorEntity=_FakeCoordinatorEntity,
    DataUpdateCoordinator=_FakeDataUpdateCoordinator,
    UpdateFailed=type("UpdateFailed", (Exception,), {}),
)
