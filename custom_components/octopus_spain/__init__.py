"""Octopus Energy Spain custom integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import OctopusSpainClient
from .const import PLATFORMS
from .coordinator import OctopusSpainCoordinator
from .model import OctopusSpainRuntimeData
from .services import async_register_services

type OctopusSpainConfigEntry = ConfigEntry[OctopusSpainRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: OctopusSpainConfigEntry) -> bool:
    """Set up Octopus Energy Spain from a config entry."""

    client = OctopusSpainClient(
        async_get_clientsession(hass),
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
    )
    coordinator = OctopusSpainCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = OctopusSpainRuntimeData(client=client, coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    async_register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OctopusSpainConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
