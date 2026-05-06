"""Binary sensor platform for Octopus Energy Spain."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import SUN_CLUB_END_HOUR, SUN_CLUB_START_HOUR
from .coordinator import OctopusSpainCoordinator
from .entity import OctopusSpainEntity

MADRID = ZoneInfo("Europe/Madrid")

SUN_CLUB_DESCRIPTION = BinarySensorEntityDescription(
    key="sun_club_window",
    translation_key="sun_club_window",
    icon="mdi:white-balance-sunny",
)
SOLAR_WALLET_DESCRIPTION = BinarySensorEntityDescription(
    key="solar_wallet",
    translation_key="solar_wallet",
    icon="mdi:solar-power-variant",
)
INTELLIGENT_GO_DEVICE_DESCRIPTION = BinarySensorEntityDescription(
    key="intelligent_go_device",
    translation_key="intelligent_go_device",
    icon="mdi:ev-plug-type2",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Octopus Spain binary sensors."""

    coordinator: OctopusSpainCoordinator = entry.runtime_data.coordinator
    async_add_entities(
        [
            OctopusSunClubWindowSensor(coordinator),
            OctopusSolarWalletSensor(coordinator),
            OctopusIntelligentGoDeviceSensor(coordinator),
        ]
    )


class OctopusSunClubWindowSensor(OctopusSpainEntity, BinarySensorEntity):
    """Indicate whether the regular Sun Club discount window is active."""

    entity_description = SUN_CLUB_DESCRIPTION

    def __init__(self, coordinator: OctopusSpainCoordinator) -> None:
        """Initialize the binary sensor."""

        super().__init__(coordinator, SUN_CLUB_DESCRIPTION.key)

    @property
    def is_on(self) -> bool:
        """Return true during the documented 12:00-18:00 Sun Club window."""

        now = datetime.now(MADRID)
        return SUN_CLUB_START_HOUR <= now.hour < SUN_CLUB_END_HOUR


class OctopusSolarWalletSensor(OctopusSpainEntity, BinarySensorEntity):
    """Indicate whether Kraken reports Solar Wallet on the account."""

    entity_description = SOLAR_WALLET_DESCRIPTION

    def __init__(self, coordinator: OctopusSpainCoordinator) -> None:
        """Initialize the binary sensor."""

        super().__init__(coordinator, SOLAR_WALLET_DESCRIPTION.key)

    @property
    def is_on(self) -> bool | None:
        """Return true when the account has Solar Wallet."""

        solar_wallet = self.coordinator.data.solar_wallet if self.coordinator.data else {}
        value = solar_wallet.get("has_solar_wallet")
        return value if isinstance(value, bool) else None


class OctopusIntelligentGoDeviceSensor(OctopusSpainEntity, BinarySensorEntity):
    """Indicate whether Kraken reports a registered KrakenFlex device."""

    entity_description = INTELLIGENT_GO_DEVICE_DESCRIPTION

    def __init__(self, coordinator: OctopusSpainCoordinator) -> None:
        """Initialize the binary sensor."""

        super().__init__(coordinator, INTELLIGENT_GO_DEVICE_DESCRIPTION.key)

    @property
    def is_on(self) -> bool | None:
        """Return true when KrakenFlex device details are present."""

        intelligent_go = self.coordinator.data.intelligent_go if self.coordinator.data else {}
        if intelligent_go.get("available") is False:
            return None
        device = intelligent_go.get("registered_device") or {}
        return bool(device.get("present"))
