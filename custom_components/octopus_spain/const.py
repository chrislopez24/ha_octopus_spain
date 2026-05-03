"""Constants for the Octopus Energy Spain integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "octopus_spain"
NAME = "Octopus Energy Spain"
MANUFACTURER = "Octopus Energy Spain"
GRAPHQL_ENDPOINT = "https://api.oees-kraken.energy/v1/graphql/"

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

UPDATE_INTERVAL = timedelta(hours=6)
INVOICE_CACHE_LIMIT = 12
SUN_CLUB_START_HOUR = 12
SUN_CLUB_END_HOUR = 18
SUN_CLUB_DISCOUNT = 0.45

CONF_ACCOUNT_NUMBER = "account_number"
CONF_PROPERTY_ID = "property_id"
CONF_LEDGER_NUMBER = "ledger_number"
CONF_AGREEMENT_ID = "agreement_id"
CONF_ACCOUNT_HASH = "account_hash"
CONF_PROPERTY_HASH = "property_hash"

ATTR_RECENT_INVOICES = "recent_invoices"
ATTR_DOCUMENT_AVAILABLE = "document_available"
