"""Data coordinator for Octopus Energy Spain."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import OctopusData, OctopusSpainAuthError, OctopusSpainClient, OctopusSpainError
from .const import (
    CONF_ACCOUNT_HASH,
    CONF_ACCOUNT_NUMBER,
    CONF_AGREEMENT_ID,
    CONF_LEDGER_NUMBER,
    CONF_PROPERTY_HASH,
    CONF_PROPERTY_ID,
    DOMAIN,
    INVOICE_CACHE_LIMIT,
    SUN_CLUB_DISCOUNT,
    SUN_CLUB_END_HOUR,
    SUN_CLUB_START_HOUR,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)
MADRID = ZoneInfo("Europe/Madrid")


class OctopusSpainCoordinator(DataUpdateCoordinator[OctopusData]):
    """Coordinate polling of redacted Octopus account data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: OctopusSpainClient,
    ) -> None:
        """Initialize the coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=UPDATE_INTERVAL,
            always_update=False,
        )
        self.client = client
        self.selection = self._selection_from_entry(entry)

    async def _async_update_data(self) -> OctopusData:
        """Fetch account, tariff, balance and invoice data."""

        try:
            agreement = await self.client.async_agreement(self.selection.agreement_id)
            billing = await self.client.async_billing_info(self.selection.account_number)
            invoices = await self.client.async_bills(
                self.selection.account_number,
                self.selection.ledger_number,
                INVOICE_CACHE_LIMIT,
            )
            credits = await self.client.async_credits(
                self.selection.account_number,
                self.selection.ledger_number,
            )
            devices = await self.client.async_devices(self.selection.account_number)
            await self.client.async_account_overview()
            await self.client.async_referrals(self.selection.account_number)
            base_energy_price = self.client.build_data(
                self.selection,
                agreement,
                billing,
                invoices,
                credits,
                devices=devices,
                measurements={},
            ).tariff.get("base_energy_price")
            end_at = datetime.combine(datetime.now(MADRID).date(), time.min, MADRID)
            start_at = end_at - timedelta(days=31)
            measurements = await self.client.async_measurement_dashboard_data(
                self.selection.property_id,
                start_at,
                end_at,
                base_energy_price,
                SUN_CLUB_DISCOUNT,
                SUN_CLUB_START_HOUR,
                SUN_CLUB_END_HOUR,
                31,
            )
        except OctopusSpainAuthError as err:
            raise ConfigEntryAuthFailed("Octopus credentials need reauthentication") from err
        except OctopusSpainError as err:
            raise UpdateFailed(f"Octopus update failed: {err}") from err
        return self.client.build_data(
            self.selection,
            agreement,
            billing,
            invoices,
            credits,
            devices=devices,
            measurements=measurements,
        )

    @staticmethod
    def _selection_from_entry(entry: ConfigEntry):
        from .api import AccountSelection

        return AccountSelection(
            account_number=entry.data[CONF_ACCOUNT_NUMBER],
            property_id=entry.data.get(CONF_PROPERTY_ID),
            ledger_number=entry.data.get(CONF_LEDGER_NUMBER),
            agreement_id=entry.data.get(CONF_AGREEMENT_ID),
            account_hash=entry.data.get(CONF_ACCOUNT_HASH, "unknown"),
            property_hash=entry.data.get(CONF_PROPERTY_HASH, "unknown"),
        )
