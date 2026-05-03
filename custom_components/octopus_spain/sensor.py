"""Sensor platform for Octopus Energy Spain."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable
from zoneinfo import ZoneInfo

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_EURO
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_RECENT_INVOICES, SUN_CLUB_DISCOUNT, SUN_CLUB_END_HOUR, SUN_CLUB_START_HOUR
from .coordinator import OctopusSpainCoordinator
from .entity import OctopusSpainEntity

MADRID = ZoneInfo("Europe/Madrid")


@dataclass(frozen=True, kw_only=True)
class OctopusSensorEntityDescription(SensorEntityDescription):
    """Description for an Octopus sensor."""

    value_fn: Callable[[OctopusSpainCoordinator], Any]
    attrs_fn: Callable[[OctopusSpainCoordinator], dict[str, Any]] | None = None


def _tariff_value(key: str) -> Callable[[OctopusSpainCoordinator], Any]:
    return lambda coordinator: (coordinator.data.tariff if coordinator.data else {}).get(key)


def _date_sensor_value(value_fn: Callable[[OctopusSpainCoordinator], Any]) -> Callable[[OctopusSpainCoordinator], date | None]:
    def wrapped(coordinator: OctopusSpainCoordinator) -> date | None:
        value = value_fn(coordinator)
        if value is None or isinstance(value, date):
            return value
        return date.fromisoformat(str(value)[:10])

    return wrapped


def _billing_value(key: str) -> Callable[[OctopusSpainCoordinator], Any]:
    return lambda coordinator: (coordinator.data.billing if coordinator.data else {}).get(key)


def _balance_value(key: str) -> Callable[[OctopusSpainCoordinator], Any]:
    return lambda coordinator: (coordinator.data.balances if coordinator.data else {}).get(key)


def _measurement_value(key: str) -> Callable[[OctopusSpainCoordinator], Any]:
    return lambda coordinator: (coordinator.data.measurements if coordinator.data else {}).get(key)


def _current_energy_price(coordinator: OctopusSpainCoordinator) -> float | None:
    base_price = (coordinator.data.tariff if coordinator.data else {}).get("base_energy_price")
    if base_price is None:
        return None
    now = datetime.now(MADRID)
    if SUN_CLUB_START_HOUR <= now.hour < SUN_CLUB_END_HOUR:
        return round(float(base_price) * (1 - SUN_CLUB_DISCOUNT), 6)
    return base_price


def _invoice_count(coordinator: OctopusSpainCoordinator) -> int:
    return len(coordinator.data.invoices if coordinator.data else [])


def _invoice_attrs(coordinator: OctopusSpainCoordinator) -> dict[str, Any]:
    if not coordinator.data:
        return {ATTR_RECENT_INVOICES: []}
    invoices = [dict(invoice) for invoice in coordinator.data.invoices]
    latest = invoices[0] if invoices else {}
    return {
        "latest_period_start": latest.get("period_start"),
        "latest_period_end": latest.get("period_end"),
        "latest_document_available": latest.get("document_available"),
        ATTR_RECENT_INVOICES: invoices,
    }


def _measurement_attrs(coordinator: OctopusSpainCoordinator) -> dict[str, Any]:
    measurements = coordinator.data.measurements if coordinator.data else {}
    return {
        "latest_period_start": measurements.get("latest_period_start"),
        "latest_period_end": measurements.get("latest_period_end"),
        "api_cost_available": measurements.get("api_cost_available"),
        "cost_preference": measurements.get("cost_preference"),
        "estimated_cost_source": measurements.get("estimated_cost_source"),
        "estimated_cost_includes_power": measurements.get("estimated_cost_includes_power"),
        "estimated_cost_includes_taxes": measurements.get("estimated_cost_includes_taxes"),
    }


def _series_attrs(coordinator: OctopusSpainCoordinator) -> dict[str, Any]:
    measurements = coordinator.data.measurements if coordinator.data else {}
    return {
        "series": measurements.get("series", {}),
        "period_series": measurements.get("period_series", {}),
        "hourly_period_series": measurements.get("hourly_period_series", {}),
        "estimated_cost_series_by_date": measurements.get("series_by_date", {}),
    }


def _credit_value(reason_code: str) -> Callable[[OctopusSpainCoordinator], Any]:
    return lambda coordinator: ((coordinator.data.credits if coordinator.data else {}).get("reason_code_amounts") or {}).get(reason_code)


def _credit_attrs(coordinator: OctopusSpainCoordinator) -> dict[str, Any]:
    credits = coordinator.data.credits if coordinator.data else {}
    return {
        "reason_code_counts": credits.get("reason_code_counts", {}),
        "reason_code_amounts": credits.get("reason_code_amounts", {}),
        "recent_credits": credits.get("recent_credits", []),
    }


SENSORS: tuple[OctopusSensorEntityDescription, ...] = (
    OctopusSensorEntityDescription(key="tariff_name", translation_key="tariff_name", value_fn=_tariff_value("name")),
    OctopusSensorEntityDescription(key="tariff_code", translation_key="tariff_code", value_fn=_tariff_value("code")),
    OctopusSensorEntityDescription(key="tariff_valid_to", translation_key="tariff_valid_to", device_class=SensorDeviceClass.DATE, value_fn=_date_sensor_value(_tariff_value("valid_to"))),
    OctopusSensorEntityDescription(key="base_energy_price", translation_key="base_energy_price", native_unit_of_measurement=f"{CURRENCY_EURO}/kWh", suggested_display_precision=4, value_fn=_tariff_value("base_energy_price")),
    OctopusSensorEntityDescription(key="current_energy_price", translation_key="current_energy_price", native_unit_of_measurement=f"{CURRENCY_EURO}/kWh", suggested_display_precision=4, value_fn=_current_energy_price),
    OctopusSensorEntityDescription(key="power_price_period_1", translation_key="power_price_period_1", native_unit_of_measurement=f"{CURRENCY_EURO}/kW/d", suggested_display_precision=4, value_fn=_tariff_value("power_price_period_1")),
    OctopusSensorEntityDescription(key="power_price_period_2", translation_key="power_price_period_2", native_unit_of_measurement=f"{CURRENCY_EURO}/kW/d", suggested_display_precision=4, value_fn=_tariff_value("power_price_period_2")),
    OctopusSensorEntityDescription(key="surplus_rate", translation_key="surplus_rate", native_unit_of_measurement=f"{CURRENCY_EURO}/kWh", suggested_display_precision=4, value_fn=_tariff_value("surplus_rate")),
    OctopusSensorEntityDescription(key="last_invoice_amount", translation_key="last_invoice_amount", device_class=SensorDeviceClass.MONETARY, native_unit_of_measurement=CURRENCY_EURO, suggested_display_precision=2, value_fn=_billing_value("last_invoice_amount")),
    OctopusSensorEntityDescription(key="last_invoice_issued", translation_key="last_invoice_issued", device_class=SensorDeviceClass.DATE, value_fn=_date_sensor_value(_billing_value("last_invoice_issued"))),
    OctopusSensorEntityDescription(key="last_invoice_period_start", translation_key="last_invoice_period_start", device_class=SensorDeviceClass.DATE, value_fn=_date_sensor_value(_billing_value("last_invoice_period_start"))),
    OctopusSensorEntityDescription(key="last_invoice_period_end", translation_key="last_invoice_period_end", device_class=SensorDeviceClass.DATE, value_fn=_date_sensor_value(_billing_value("last_invoice_period_end"))),
    OctopusSensorEntityDescription(key="credit_balance", translation_key="credit_balance", device_class=SensorDeviceClass.MONETARY, native_unit_of_measurement=CURRENCY_EURO, suggested_display_precision=2, value_fn=_balance_value("credit_balance")),
    OctopusSensorEntityDescription(key="sun_club_credits", translation_key="sun_club_credits", device_class=SensorDeviceClass.MONETARY, native_unit_of_measurement=CURRENCY_EURO, suggested_display_precision=2, value_fn=_credit_value("SUN_CLUB"), attrs_fn=_credit_attrs),
    OctopusSensorEntityDescription(key="referral_credits", translation_key="referral_credits", device_class=SensorDeviceClass.MONETARY, native_unit_of_measurement=CURRENCY_EURO, suggested_display_precision=2, value_fn=_credit_value("REFERRAL_REWARD"), attrs_fn=_credit_attrs),
    OctopusSensorEntityDescription(key="last_complete_day_consumption", translation_key="last_complete_day_consumption", device_class=SensorDeviceClass.ENERGY, native_unit_of_measurement="kWh", suggested_display_precision=3, value_fn=_measurement_value("last_day_consumption_kwh"), attrs_fn=_measurement_attrs),
    OctopusSensorEntityDescription(key="last_complete_day_api_cost", translation_key="last_complete_day_api_cost", device_class=SensorDeviceClass.MONETARY, native_unit_of_measurement=CURRENCY_EURO, suggested_display_precision=2, value_fn=_measurement_value("last_day_cost_eur"), attrs_fn=_measurement_attrs),
    OctopusSensorEntityDescription(key="last_complete_day_estimated_cost", translation_key="last_complete_day_estimated_cost", device_class=SensorDeviceClass.MONETARY, native_unit_of_measurement=CURRENCY_EURO, suggested_display_precision=2, value_fn=_measurement_value("estimated_last_day_cost_eur"), attrs_fn=_measurement_attrs),
    OctopusSensorEntityDescription(key="week_consumption", translation_key="week_consumption", device_class=SensorDeviceClass.ENERGY, native_unit_of_measurement="kWh", suggested_display_precision=3, value_fn=_measurement_value("last_7_days_consumption_kwh"), attrs_fn=_measurement_attrs),
    OctopusSensorEntityDescription(key="week_estimated_cost", translation_key="week_estimated_cost", device_class=SensorDeviceClass.MONETARY, native_unit_of_measurement=CURRENCY_EURO, suggested_display_precision=2, value_fn=_measurement_value("estimated_last_7_days_cost_eur"), attrs_fn=_measurement_attrs),
    OctopusSensorEntityDescription(key="month_consumption", translation_key="month_consumption", device_class=SensorDeviceClass.ENERGY, native_unit_of_measurement="kWh", suggested_display_precision=3, value_fn=_measurement_value("last_31_days_consumption_kwh"), attrs_fn=_measurement_attrs),
    OctopusSensorEntityDescription(key="month_estimated_cost", translation_key="month_estimated_cost", device_class=SensorDeviceClass.MONETARY, native_unit_of_measurement=CURRENCY_EURO, suggested_display_precision=2, value_fn=_measurement_value("estimated_last_31_days_cost_eur"), attrs_fn=_measurement_attrs),
    OctopusSensorEntityDescription(key="measurement_points", translation_key="measurement_points", value_fn=_measurement_value("points_count"), attrs_fn=_measurement_attrs),
    OctopusSensorEntityDescription(key="measurement_series", translation_key="measurement_series", value_fn=_measurement_value("points_count"), attrs_fn=_series_attrs),
    OctopusSensorEntityDescription(key="invoices", translation_key="invoices", value_fn=_invoice_count, attrs_fn=_invoice_attrs),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Octopus Spain sensors."""

    coordinator: OctopusSpainCoordinator = entry.runtime_data.coordinator
    async_add_entities(OctopusSensor(coordinator, description) for description in SENSORS)


class OctopusSensor(OctopusSpainEntity, SensorEntity):
    """Octopus Spain sensor."""

    entity_description: OctopusSensorEntityDescription

    def __init__(
        self,
        coordinator: OctopusSpainCoordinator,
        description: OctopusSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""

        self.entity_description = description
        super().__init__(coordinator, description.key)

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""

        return self.entity_description.value_fn(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return redacted extra attributes."""

        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator)
