"""Data coordinator for Octopus Energy Spain."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
import logging
from typing import Any, Awaitable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_track_point_in_time
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
            always_update=True,
        )
        self.client = client
        self.selection = self._selection_from_entry(entry)
        self._aligned_refresh_active = False
        self._unsub_aligned_refresh = None

    def async_start_aligned_refresh(self) -> None:
        """Start refreshing on Madrid hour boundaries."""

        self._aligned_refresh_active = True
        self._schedule_next_aligned_refresh()

    def async_stop_aligned_refresh(self) -> None:
        """Stop the aligned refresh timer."""

        self._aligned_refresh_active = False
        if self._unsub_aligned_refresh is not None:
            self._unsub_aligned_refresh()
            self._unsub_aligned_refresh = None

    def _schedule_next_aligned_refresh(self) -> None:
        """Schedule the next refresh at the next Madrid hour boundary."""

        if not self._aligned_refresh_active:
            return
        if self._unsub_aligned_refresh is not None:
            self._unsub_aligned_refresh()
        self._unsub_aligned_refresh = async_track_point_in_time(
            self.hass,
            self._async_aligned_refresh,
            next_madrid_hour(),
        )

    async def _async_aligned_refresh(self, _now: datetime) -> None:
        """Refresh data and schedule the next Madrid hour boundary."""

        self._unsub_aligned_refresh = None
        try:
            await self.async_request_refresh()
        finally:
            self._schedule_next_aligned_refresh()

    async def _async_update_data(self) -> OctopusData:
        """Fetch account, tariff, balance and invoice data."""

        try:
            agreement = await self.client.async_agreement(self.selection.agreement_id)
            billing = await self.client.async_billing_info(self.selection.account_number)
            invoices = await self._optional_data(
                "invoices",
                self.client.async_bills(
                    self.selection.account_number,
                    self.selection.ledger_number,
                    INVOICE_CACHE_LIMIT,
                ),
                [],
            )
            credits = await self._optional_data(
                "credits",
                self.client.async_credits(
                    self.selection.account_number,
                    self.selection.ledger_number,
                ),
                {},
            )
            solar_wallet = await self._optional_data(
                "solar_wallet",
                self.client.async_solar_wallet(
                    self.selection.account_number,
                    self.selection.ledger_number,
                ),
                {"available": False, "error": "unavailable"},
            )
            intelligent_go = await self._optional_data(
                "intelligent_go",
                self.client.async_intelligent_go(
                    self.selection.account_number,
                    self.selection.property_id,
                ),
                {"available": False, "error": "unavailable"},
            )
            tariff = self.client.build_data(
                self.selection,
                agreement,
                billing,
                invoices,
                credits,
                measurements={},
                solar_wallet=solar_wallet,
                intelligent_go=intelligent_go,
            ).tariff
            end_at = datetime.combine(datetime.now(MADRID).date(), time.min, MADRID)
            start_at = end_at - timedelta(days=31)
            measurements = await self.client.async_measurement_dashboard_data(
                self.selection.property_id,
                start_at,
                end_at,
                variable_prices=tariff.get("period_prices"),
                base_energy_price=tariff.get("base_energy_price"),
                sun_club_enabled=bool(tariff.get("sun_club_enabled")),
                sun_club_discount=SUN_CLUB_DISCOUNT,
                sun_club_start_hour=SUN_CLUB_START_HOUR,
                sun_club_end_hour=SUN_CLUB_END_HOUR,
                days=31,
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
            measurements=measurements,
            solar_wallet=solar_wallet,
            intelligent_go=intelligent_go,
        )

    async def _optional_data(
        self, name: str, request: Awaitable[Any], empty: Any
    ) -> Any:
        """Return optional data or retain its last valid value on failure."""

        try:
            return await request
        except OctopusSpainAuthError:
            raise
        except OctopusSpainError as err:
            _LOGGER.warning(
                "Optional Octopus data %s is unavailable (%s)",
                name,
                err.__class__.__name__,
            )
            previous = self.data
            value = getattr(previous, name, None) if previous is not None else None
            if value:
                retained = value.copy() if isinstance(value, dict) else list(value)
                if isinstance(retained, dict):
                    retained["stale"] = True
                    retained["error"] = "unavailable"
                return retained
            return empty.copy() if isinstance(empty, (dict, list)) else empty

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


def next_madrid_hour(now: datetime | None = None) -> datetime:
    """Return the next whole-hour boundary in Europe/Madrid."""

    madrid_now = (now or datetime.now(MADRID)).astimezone(MADRID)
    return madrid_now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
