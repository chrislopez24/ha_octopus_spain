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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Octopus Spain binary sensors."""

    coordinator: OctopusSpainCoordinator = entry.runtime_data.coordinator
    async_add_entities([OctopusSunClubWindowSensor(coordinator)])


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
