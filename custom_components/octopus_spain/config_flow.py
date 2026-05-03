"""Config flow for Octopus Energy Spain."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .api import OctopusSpainAuthError, OctopusSpainClient, OctopusSpainError
from .const import (
    CONF_ACCOUNT_HASH,
    CONF_ACCOUNT_NUMBER,
    CONF_AGREEMENT_ID,
    CONF_LEDGER_NUMBER,
    CONF_PROPERTY_HASH,
    CONF_PROPERTY_ID,
    DOMAIN,
)


def _schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_EMAIL, default=defaults.get(CONF_EMAIL, "")): TextSelector(
                TextSelectorConfig(type=TextSelectorType.EMAIL)
            ),
            vol.Required(CONF_PASSWORD): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
        }
    )


async def _validate_input(hass: HomeAssistant, user_input: dict[str, Any]) -> dict[str, Any]:
    client = OctopusSpainClient(
        async_get_clientsession(hass),
        user_input[CONF_EMAIL],
        user_input[CONF_PASSWORD],
    )
    selection = await client.async_validate_login()
    return {
        CONF_EMAIL: user_input[CONF_EMAIL],
        CONF_PASSWORD: user_input[CONF_PASSWORD],
        CONF_ACCOUNT_NUMBER: selection.account_number,
        CONF_PROPERTY_ID: selection.property_id,
        CONF_LEDGER_NUMBER: selection.ledger_number,
        CONF_AGREEMENT_ID: selection.agreement_id,
        CONF_ACCOUNT_HASH: selection.account_hash,
        CONF_PROPERTY_HASH: selection.property_hash,
    }


class OctopusSpainConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the Octopus Energy Spain config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle a flow initialized by the user."""

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                data = await _validate_input(self.hass, user_input)
            except OctopusSpainAuthError:
                errors["base"] = "invalid_auth"
            except OctopusSpainError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(data[CONF_ACCOUNT_HASH])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Octopus Energy Spain", data=data)

        return self.async_show_form(step_id="user", data_schema=_schema(user_input), errors=errors)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Handle reauthentication requested by the coordinator."""

        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm new credentials for an existing entry."""

        errors: dict[str, str] = {}
        entry = self._reauth_entry
        defaults = {CONF_EMAIL: entry.data.get(CONF_EMAIL, "")} if entry else {}
        if user_input is not None and entry is not None:
            merged_input = {**user_input, CONF_EMAIL: user_input.get(CONF_EMAIL) or defaults[CONF_EMAIL]}
            try:
                data = await _validate_input(self.hass, merged_input)
            except OctopusSpainAuthError:
                errors["base"] = "invalid_auth"
            except OctopusSpainError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(data[CONF_ACCOUNT_HASH])
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(entry, data_updates=data)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_schema(defaults),
            errors=errors,
        )
