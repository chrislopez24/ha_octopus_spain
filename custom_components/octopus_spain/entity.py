"""Entity helpers for Octopus Energy Spain."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, NAME
from .coordinator import OctopusSpainCoordinator


class OctopusSpainEntity(CoordinatorEntity[OctopusSpainCoordinator]):
    """Base entity for Octopus Spain coordinator entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: OctopusSpainCoordinator, key: str) -> None:
        """Initialize the entity."""

        super().__init__(coordinator)
        self.entity_description = getattr(self, "entity_description", None)
        account_hash = coordinator.selection.account_hash
        self._attr_unique_id = f"{DOMAIN}_{account_hash}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, account_hash)},
            manufacturer=MANUFACTURER,
            name=NAME,
        )
