"""Data models for Octopus Energy Spain."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .api import OctopusSpainClient
    from .coordinator import OctopusSpainCoordinator


@dataclass(slots=True)
class AccountSelection:
    """Selected account/property identifiers kept inside config entry data."""

    account_number: str
    property_id: str | None = None
    ledger_number: str | None = None
    agreement_id: str | None = None
    account_hash: str = ""
    property_hash: str = ""


@dataclass(slots=True)
class InvoiceDocument:
    """Invoice document reference returned on demand only."""

    invoice_id_hash: str
    url: str


@dataclass(slots=True)
class OctopusData:
    """Redacted integration data used by coordinator entities."""

    account_hash: str
    property_hash: str
    tariff: dict[str, Any] = field(default_factory=dict)
    billing: dict[str, Any] = field(default_factory=dict)
    invoices: list[dict[str, Any]] = field(default_factory=list)
    balances: dict[str, Any] = field(default_factory=dict)
    credits: dict[str, Any] = field(default_factory=dict)
    measurements: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class OctopusSpainRuntimeData:
    """Runtime data stored in the config entry."""

    client: "OctopusSpainClient"
    coordinator: "OctopusSpainCoordinator"
