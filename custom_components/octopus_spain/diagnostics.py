"""Diagnostics support for Octopus Energy Spain."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.components.diagnostics import async_redact_data

from .const import (
    CONF_ACCOUNT_NUMBER,
    CONF_AGREEMENT_ID,
    CONF_LEDGER_NUMBER,
    CONF_PROPERTY_ID,
)

TO_REDACT = {
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_ACCOUNT_NUMBER,
    CONF_PROPERTY_ID,
    CONF_LEDGER_NUMBER,
    CONF_AGREEMENT_ID,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return redacted diagnostics for a config entry."""

    return {
        "entry": async_redact_data(entry.data, TO_REDACT),
        "coordinator_data": getattr(getattr(entry, "runtime_data", None), "coordinator", None).data
        if getattr(entry, "runtime_data", None)
        else None,
    }
