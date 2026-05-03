"""Home Assistant service handlers for Octopus Energy Spain."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .api import OctopusSpainError
from .const import DOMAIN
from .model import OctopusSpainRuntimeData
from .const import SUN_CLUB_DISCOUNT, SUN_CLUB_END_HOUR, SUN_CLUB_START_HOUR
from .service_helpers import madrid_midnight_range, service_date_range

GET_INVOICE_DOCUMENT_SCHEMA = vol.Schema({vol.Required("invoice_id_hash"): cv.string})
GET_INVOICE_DOCUMENT_BY_INDEX_SCHEMA = vol.Schema(
    {vol.Required("index"): vol.All(int, vol.Range(min=0, max=23))}
)
GET_INVOICES_SCHEMA = vol.Schema(
    {vol.Optional("limit", default=12): vol.All(int, vol.Range(min=1, max=24))}
)
GET_MEASUREMENTS_SCHEMA = vol.Schema(
    {
        vol.Optional("start_date"): cv.date,
        vol.Optional("end_date"): cv.date,
        vol.Optional("frequency", default="DAY_INTERVAL"): vol.In(["DAY_INTERVAL", "HOUR_INTERVAL"]),
    }
)

def async_register_services(hass: HomeAssistant) -> None:
    """Register integration services once."""

    if hass.services.has_service(DOMAIN, "get_invoice_document"):
        return

    hass.services.async_register(
        DOMAIN,
        "get_invoice_document",
        _async_get_invoice_document(hass),
        schema=GET_INVOICE_DOCUMENT_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "get_invoices",
        _async_get_invoices(hass),
        schema=GET_INVOICES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "get_latest_invoice_document",
        _async_get_invoice_document_by_index(hass, default_index=0),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "get_invoice_document_by_index",
        _async_get_invoice_document_by_index(hass),
        schema=GET_INVOICE_DOCUMENT_BY_INDEX_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "get_measurements",
        _async_get_measurements(hass),
        schema=GET_MEASUREMENTS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

def _async_get_invoice_document(hass: HomeAssistant):
    async def handler(call: ServiceCall) -> ServiceResponse:
        """Return a signed invoice URL on demand without persisting it in state."""

        runtime = runtime_data_for_invoice_hash(hass, call.data["invoice_id_hash"])
        try:
            document = await runtime.client.async_get_invoice_document(call.data["invoice_id_hash"])
        except OctopusSpainError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invoice_document_unavailable",
            ) from err
        return {"invoice_id_hash": document.invoice_id_hash, "url": document.url}

    return handler


def _async_get_invoice_document_by_index(hass: HomeAssistant, default_index: int | None = None):
    async def handler(call: ServiceCall) -> ServiceResponse:
        """Return a signed invoice URL by recent invoice index."""

        runtime = first_runtime_data(hass)
        index = default_index if default_index is not None else call.data["index"]
        try:
            document = await runtime.client.async_get_invoice_document_by_index(index)
        except OctopusSpainError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invoice_document_unavailable",
            ) from err
        return {"index": index, "invoice_id_hash": document.invoice_id_hash, "url": document.url}

    return handler


def _async_get_invoices(hass: HomeAssistant):
    async def handler(call: ServiceCall) -> ServiceResponse:
        """Return a redacted list of recent invoices."""

        runtime = first_runtime_data(hass)
        selection = runtime.coordinator.selection
        try:
            return await runtime.client.async_get_invoices_response(
                selection.account_number,
                selection.ledger_number,
                call.data["limit"],
            )
        except OctopusSpainError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invoices_unavailable",
            ) from err

    return handler


def _async_get_measurements(hass: HomeAssistant):
    async def handler(call: ServiceCall) -> ServiceResponse:
        """Return redacted consumption/cost measurements for a date range."""

        runtime = first_runtime_data(hass)
        selection = runtime.coordinator.selection
        service_range = service_date_range(call.data)
        try:
            if call.data["frequency"] == "DAY_INTERVAL":
                start_at, end_at = madrid_midnight_range(service_range)
                base_energy_price = (runtime.coordinator.data.tariff if runtime.coordinator.data else {}).get("base_energy_price")
                return {
                    "frequency": call.data["frequency"],
                    **await runtime.client.async_measurement_dashboard_data(
                        selection.property_id,
                        start_at,
                        end_at,
                        base_energy_price,
                        SUN_CLUB_DISCOUNT,
                        SUN_CLUB_START_HOUR,
                        SUN_CLUB_END_HOUR,
                        max(1, (service_range.end - service_range.start).days),
                    ),
                }
            return await runtime.client.async_get_measurements_response(
                selection.property_id,
                service_range.start,
                service_range.end,
                call.data["frequency"],
            )
        except OctopusSpainError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="measurements_unavailable",
            ) from err

    return handler


def first_runtime_data(hass: HomeAssistant) -> OctopusSpainRuntimeData:
    """Return runtime data for the first configured Octopus entry."""

    for runtime in iter_runtime_data(hass):
        return runtime
    raise HomeAssistantError("Octopus Spain is not configured")


def iter_runtime_data(hass: HomeAssistant):
    """Yield runtime data for loaded Octopus entries."""

    for entry in hass.config_entries.async_entries(DOMAIN):
        runtime: Any = getattr(entry, "runtime_data", None)
        if runtime is not None:
            yield runtime


def runtime_data_for_invoice_hash(hass: HomeAssistant, invoice_id_hash: str) -> OctopusSpainRuntimeData:
    """Return the runtime data whose coordinator currently exposes an invoice hash."""

    fallback: OctopusSpainRuntimeData | None = None
    for runtime in iter_runtime_data(hass):
        fallback = fallback or runtime
        invoices = runtime.coordinator.data.invoices if runtime.coordinator.data else []
        if any(invoice.get("invoice_id_hash") == invoice_id_hash for invoice in invoices):
            return runtime
        invoice_id_cache = getattr(runtime.client, "_invoice_id_cache", {})
        if invoice_id_hash in invoice_id_cache:
            return runtime
    if fallback is not None:
        return fallback
    raise HomeAssistantError("Octopus Spain is not configured")
