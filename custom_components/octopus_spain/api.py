"""Async Octopus Energy Spain GraphQL client."""

from __future__ import annotations

import asyncio
import base64
from datetime import date, datetime, timezone
import json
import logging
import time
from typing import Any
from zoneinfo import ZoneInfo

from aiohttp import ClientError, ClientResponseError, ClientSession

from .const import GRAPHQL_ENDPOINT, INVOICE_CACHE_LIMIT
from .graphql_queries import (
    AGREEMENT_QUERY,
    AUTH_MUTATION,
    BILL_QUERY,
    BILLING_INFO_QUERY,
    BILLS_QUERY,
    CREDITS_QUERY,
    DEVICES_QUERY,
    LINKED_SUPPLY_SAFE_QUERY,
    MEASUREMENTS_QUERY,
    REFERRALS_SAFE_QUERY,
    VIEWER_ACCOUNT_QUERY,
    VIEWER_PROPERTY_QUERY,
    VIEWER_SAFE_QUERY,
)
from .measurements import estimated_energy_costs_from_hourly
from .mappers import (
    build_data,
    first_edge_node,
    select_default_account,
    summarize_credits,
    summarize_devices,
    summarize_linked_supply,
    summarize_measurements,
    summarize_referrals,
    summarize_viewer,
)
from .model import AccountSelection, InvoiceDocument, OctopusData
from .redaction import redact_sensitive_value, stable_hash

_LOGGER = logging.getLogger(__name__)
MADRID = ZoneInfo("Europe/Madrid")
TOKEN_REFRESH_MARGIN_SECONDS = 300
REFRESH_TOKEN_REFRESH_MARGIN_SECONDS = 86400


class OctopusSpainError(Exception):
    """Base error for Octopus Spain API failures."""


class OctopusSpainAuthError(OctopusSpainError):
    """Authentication failed or token expired."""


class OctopusSpainGraphQLError(OctopusSpainError):
    """GraphQL returned an application-level error."""


def _iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _invoice_period_label(period_start: str | None, period_end: str | None) -> str | None:
    if period_start and period_end:
        return f"{period_start} a {period_end}"
    return period_start or period_end


class OctopusSpainClient:
    """Purpose-built async client for the observed Kraken GraphQL API."""

    def __init__(self, session: ClientSession, email: str, password: str) -> None:
        """Initialize the client."""

        self._session = session
        self._email = email
        self._password = password
        self._token: str | None = None
        self._token_expires_at: int | None = None
        self._refresh_token: str | None = None
        self._refresh_expires_at: int | None = None
        self._login_lock = asyncio.Lock()
        self._invoice_id_cache: dict[str, int] = {}
        self._invoice_hashes: list[str] = []
        self._account_number: str | None = None
        self._ledger_number: str | None = None

    @property
    def session(self) -> ClientSession:
        """Return the shared HTTP session."""

        return self._session

    async def async_login(self, *, force_password: bool = False) -> None:
        """Authenticate and keep the Kraken token in memory only."""

        async with self._login_lock:
            if not force_password and not self._token_expires_soon():
                return
            if not force_password and self._can_use_refresh_token():
                try:
                    await self._async_obtain_token({"refreshToken": self._refresh_token}, used_refresh_token=True)
                    return
                except OctopusSpainAuthError:
                    self._refresh_token = None
                    self._refresh_expires_at = None

            await self._async_obtain_token(
                {"email": self._email, "password": self._password},
                used_refresh_token=False,
            )

    async def _async_obtain_token(self, token_input: dict[str, Any], *, used_refresh_token: bool) -> None:
        """Obtain a Kraken JWT and optional refresh token."""

        data = await self._post(
            {
                "operationName": "obtainKrakenToken",
                "query": AUTH_MUTATION,
                "variables": {"input": token_input},
            },
            include_auth=False,
        )
        auth_data = ((data.get("data") or {}).get("obtainKrakenToken") or {})
        token = auth_data.get("token")
        if not token:
            raise OctopusSpainAuthError("Octopus did not return an authentication token")
        self._token = token
        self._token_expires_at = self._jwt_expiration(token)

        refresh_token = auth_data.get("refreshToken")
        if refresh_token:
            self._refresh_token = refresh_token
        elif not used_refresh_token:
            self._refresh_token = None

        refresh_expires_at = self._coerce_timestamp(auth_data.get("refreshExpiresIn"))
        if refresh_expires_at:
            self._refresh_expires_at = refresh_expires_at
        elif not used_refresh_token:
            self._refresh_expires_at = None

    async def async_validate_login(self) -> AccountSelection:
        """Validate credentials and return a default account selection."""

        await self.async_login()
        return self.select_default_account(await self.async_viewer_account(), await self.async_viewer_property())

    async def async_viewer_account(self) -> dict[str, Any]:
        """Fetch account/ledger data."""

        return await self.async_graphql("ViewerAccount", VIEWER_ACCOUNT_QUERY, {})

    async def async_viewer_property(self) -> dict[str, Any]:
        """Fetch property/supply point data without requesting CUPS."""

        return await self.async_graphql("ViewerProperty", VIEWER_PROPERTY_QUERY, {})

    async def async_account_overview(self) -> dict[str, Any]:
        """Fetch a redacted dashboard/account overview."""

        viewer = await self.async_graphql("Viewer", VIEWER_SAFE_QUERY, {})
        linked = await self.async_graphql("LinkedSupplyPointAccounts", LINKED_SUPPLY_SAFE_QUERY, {})
        return {"viewer": summarize_viewer(viewer), "linked_supply": summarize_linked_supply(linked)}

    async def async_agreement(self, agreement_id: str | None) -> dict[str, Any]:
        """Fetch tariff agreement data."""

        if not agreement_id:
            return {}
        return await self.async_graphql("Agreement", AGREEMENT_QUERY, {"id": agreement_id})

    async def async_billing_info(self, account_number: str) -> dict[str, Any]:
        """Fetch latest billing statement details."""

        return await self.async_graphql("BillingInfo", BILLING_INFO_QUERY, {"accountNumber": account_number})

    async def async_bills(
        self, account_number: str, ledger_number: str | None, limit: int = INVOICE_CACHE_LIMIT
    ) -> list[dict[str, Any]]:
        """Fetch recent invoices and cache sensitive IDs/URLs only in memory."""

        if not ledger_number:
            return []
        payload = await self._async_bills_payload(account_number, ledger_number, max(1, min(limit, 24)))
        return self._redact_invoice_payload(payload, account_number, ledger_number)

    async def async_get_invoices_response(
        self, account_number: str, ledger_number: str | None, limit: int = INVOICE_CACHE_LIMIT
    ) -> dict[str, Any]:
        """Return redacted invoice list for a Home Assistant response service."""

        invoices = await self.async_bills(account_number, ledger_number, limit)
        return {"count": len(invoices), "invoices": invoices}

    async def async_get_invoice_document(self, invoice_id_hash: str) -> InvoiceDocument:
        """Return a fresh temporary signed invoice URL."""

        invoice_id = self._invoice_id_cache.get(invoice_id_hash)
        if not invoice_id or not self._account_number or not self._ledger_number:
            raise OctopusSpainError("Invoice document is not available; refresh invoices first")
        url = await self._async_fetch_bill_url(self._account_number, self._ledger_number, invoice_id)
        return InvoiceDocument(invoice_id_hash=invoice_id_hash, url=url)

    async def async_get_invoice_document_by_index(self, index: int) -> InvoiceDocument:
        """Return a temporary signed invoice URL by recent invoice index."""

        if index < 0 or index >= len(self._invoice_hashes):
            raise OctopusSpainError("Invoice index is not available; refresh invoices first")
        return await self.async_get_invoice_document(self._invoice_hashes[index])

    async def async_credits(self, account_number: str, ledger_number: str | None) -> dict[str, Any]:
        """Fetch credit transaction summary without exposing transaction IDs."""

        if not ledger_number:
            return {}
        payload = await self.async_graphql(
            "AccountCreditsQuery",
            CREDITS_QUERY,
            {"accountNumber": account_number, "ledgerNumber": ledger_number, "after": None},
        )
        return summarize_credits(payload)

    async def async_devices(self, account_number: str) -> dict[str, Any]:
        """Fetch Octopus account devices as a safe summary."""

        return summarize_devices(await self.async_graphql("getDevices", DEVICES_QUERY, {"accountNumber": account_number}))

    async def async_referrals(self, account_number: str) -> dict[str, Any]:
        """Fetch referral metadata as a safe summary without referral URL or names."""

        payload = await self.async_graphql(
            "AccountReferrals",
            REFERRALS_SAFE_QUERY,
            {"accountNumber": account_number, "first": 5, "after": None},
        )
        return summarize_referrals(payload)

    async def async_measurements(
        self,
        property_id: str | None,
        start_at: datetime,
        end_at: datetime,
        frequency: str = "DAY_INTERVAL",
        first: int = 31,
    ) -> dict[str, Any]:
        """Fetch consumption/cost measurements as safe aggregate data."""

        if not property_id:
            return {}
        variables = self._measurement_variables(property_id, start_at, end_at, frequency, first)
        payload = await self.async_graphql("getAccountMeasurements", MEASUREMENTS_QUERY, variables)
        return summarize_measurements(payload)

    async def async_measurement_dashboard_data(
        self,
        property_id: str | None,
        start_at: datetime,
        end_at: datetime,
        base_energy_price: float | None,
        sun_club_discount: float,
        sun_club_start_hour: int,
        sun_club_end_hour: int,
        days: int = 31,
    ) -> dict[str, Any]:
        """Fetch daily and hourly measurements enriched for HA dashboards."""

        daily = await self.async_measurements(property_id, start_at, end_at, "DAY_INTERVAL", days)
        hourly_first = max(1, min(744, int((end_at - start_at).total_seconds() // 3600) + 1))
        hourly = await self.async_measurements(property_id, start_at, end_at, "HOUR_INTERVAL", hourly_first)
        estimated = estimated_energy_costs_from_hourly(
            daily.get("points", []),
            hourly.get("points", []),
            base_energy_price=base_energy_price,
            sun_club_discount=sun_club_discount,
            sun_club_start_hour=sun_club_start_hour,
            sun_club_end_hour=sun_club_end_hour,
        )
        return {
            **daily,
            **estimated,
            "hourly_points_count": hourly.get("points_count"),
            "hourly_period_series": hourly.get("period_series", {}),
            "cost_preference": "api" if daily.get("api_cost_available") else "estimated",
        }

    async def async_get_measurements_response(
        self,
        property_id: str | None,
        start_date: date,
        end_date: date,
        frequency: str,
    ) -> dict[str, Any]:
        """Return redacted measurements for a Home Assistant response service."""

        start_at = datetime.combine(start_date, datetime.min.time(), MADRID)
        end_at = datetime.combine(end_date, datetime.min.time(), MADRID)
        if end_at <= start_at:
            raise OctopusSpainError("end_date must be after start_date")
        interval_seconds = 3600 if frequency == "HOUR_INTERVAL" else 86400
        max_points = 744 if frequency == "HOUR_INTERVAL" else 366
        first = max(1, min(max_points, int((end_at - start_at).total_seconds() // interval_seconds) + 1))
        return {"frequency": frequency, **await self.async_measurements(property_id, start_at, end_at, frequency, first)}

    async def async_graphql(self, operation_name: str, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        """Execute an authenticated GraphQL operation."""

        if self._token_expires_soon():
            await self.async_login()
        payload = {"operationName": operation_name, "query": query, "variables": variables}
        try:
            return await self._post(payload, include_auth=True)
        except OctopusSpainAuthError:
            self._token = None
            self._token_expires_at = None
            await self.async_login()
            return await self._post(payload, include_auth=True)

    async def _post(self, payload: dict[str, Any], include_auth: bool) -> dict[str, Any]:
        headers = {"content-type": "application/json"}
        if include_auth:
            if not self._token:
                raise OctopusSpainAuthError("Missing authentication token")
            headers["authorization"] = self._token
        try:
            response = await asyncio.wait_for(
                self._session.post(GRAPHQL_ENDPOINT, json=payload, headers=headers),
                timeout=30,
            )
            async with response:
                if response.status in (401, 403):
                    raise OctopusSpainAuthError("Octopus rejected the current credentials")
                response.raise_for_status()
                data = await response.json(content_type=None)
        except ClientResponseError as err:
            _LOGGER.debug("Octopus GraphQL HTTP error for %s: %s", payload.get("operationName"), err.status)
            raise OctopusSpainError(f"Octopus HTTP error {err.status}") from err
        except ClientError as err:
            _LOGGER.debug("Octopus GraphQL transport error for %s", payload.get("operationName"))
            raise OctopusSpainError("Cannot connect to Octopus") from err
        return self._handle_graphql_response(payload.get("operationName"), data)

    def _handle_graphql_response(self, operation_name: str | None, data: dict[str, Any]) -> dict[str, Any]:
        errors = data.get("errors") or []
        if not errors:
            return data
        safe_messages = [redact_sensitive_value(error.get("message", "GraphQL error")) for error in errors]
        message = "; ".join(str(item) for item in safe_messages)
        lowered = message.lower()
        _LOGGER.debug("Octopus GraphQL error for %s: %s", operation_name, message)
        if "auth" in lowered or "token" in lowered or "permission" in lowered or "jwt" in lowered:
            raise OctopusSpainAuthError("Octopus authentication failed")
        raise OctopusSpainGraphQLError(message)

    def _token_expires_soon(self) -> bool:
        if not self._token:
            return True
        if self._token_expires_at is None:
            return False
        return self._token_expires_at <= int(time.time()) + TOKEN_REFRESH_MARGIN_SECONDS

    def _can_use_refresh_token(self) -> bool:
        if not self._refresh_token:
            return False
        if self._refresh_expires_at is None:
            return True
        return self._refresh_expires_at > int(time.time()) + REFRESH_TOKEN_REFRESH_MARGIN_SECONDS

    @staticmethod
    def _jwt_expiration(token: str) -> int | None:
        parts = token.split(".")
        if len(parts) < 2:
            return None
        try:
            payload_segment = parts[1] + "=" * (-len(parts[1]) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_segment.encode()).decode())
        except (json.JSONDecodeError, TypeError, UnicodeDecodeError, ValueError):
            return None
        return OctopusSpainClient._coerce_timestamp(payload.get("exp"))

    @staticmethod
    def _coerce_timestamp(value: Any) -> int | None:
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return None

    async def _async_bills_payload(self, account_number: str, ledger_number: str, limit: int) -> dict[str, Any]:
        return await self.async_graphql(
            "Bills",
            BILLS_QUERY,
            {"accountNumber": account_number, "ledgerNumber": ledger_number, "first": limit, "after": None},
        )

    async def _async_fetch_bill_url(self, account_number: str, ledger_number: str, invoice_id: int) -> str:
        payload = await self.async_graphql(
            "Bill",
            BILL_QUERY,
            {"accountNumber": account_number, "ledgerNumber": ledger_number, "statementId": invoice_id, "after": None},
        )
        ledgers = (((payload.get("data") or {}).get("account") or {}).get("ledgers")) or []
        ledger = ledgers[0] if ledgers else {}
        node = first_edge_node(ledger.get("invoices")) or first_edge_node(ledger.get("statements")) or {}
        url = node.get("pdfUrl")
        if not url:
            raise OctopusSpainError("Invoice document URL was not returned")
        return url

    def _redact_invoice_payload(
        self, payload: dict[str, Any], account_number: str, ledger_number: str
    ) -> list[dict[str, Any]]:
        ledgers = (((payload.get("data") or {}).get("account") or {}).get("ledgers")) or []
        invoices = (((ledgers[0].get("invoices") or {}).get("edges")) if ledgers else []) or []
        redacted = [
            self._redact_invoice_node(index, edge.get("node") or {}, account_number, ledger_number)
            for index, edge in enumerate(invoices)
        ]
        self._invoice_hashes = [invoice["invoice_id_hash"] for invoice in redacted if invoice.get("invoice_id_hash")]
        return redacted

    def _redact_invoice_node(
        self, index: int, node: dict[str, Any], account_number: str, ledger_number: str
    ) -> dict[str, Any]:
        raw_invoice_id = node.get("id")
        invoice_id = str(raw_invoice_id or node.get("number") or "")
        invoice_hash = stable_hash(invoice_id)
        pdf_url = node.get("pdfUrl")
        if raw_invoice_id:
            self._invoice_id_cache[invoice_hash] = int(raw_invoice_id)
            self._account_number = account_number
            self._ledger_number = ledger_number
        period_start = self._date_only(node.get("consumptionStartDate"))
        period_end = self._date_only(node.get("consumptionEndDate"))
        period_label = _invoice_period_label(period_start, period_end)
        return {
            "index": index,
            "invoice_id_hash": invoice_hash,
            "label": f"Factura {period_label}" if period_label else f"Factura #{index + 1}",
            "period_label": period_label,
            "period_start": period_start,
            "period_end": period_end,
            "document_available": bool(pdf_url or raw_invoice_id),
        }

    @staticmethod
    def _date_only(value: str | None) -> str | None:
        from .mappers import date_only

        return date_only(value)

    @staticmethod
    def _measurement_variables(
        property_id: str, start_at: datetime, end_at: datetime, frequency: str, first: int
    ) -> dict[str, Any]:
        return {
            "propertyId": property_id,
            "first": max(1, min(first, 366 if frequency == "DAY_INTERVAL" else 744)),
            "startAt": _iso_z(start_at),
            "endAt": _iso_z(end_at),
            "timezone": "Europe/Madrid",
            "utilityFilters": [
                {"electricityFilters": {"readingDirection": "CONSUMPTION", "readingFrequencyType": frequency}}
            ],
        }

    select_default_account = staticmethod(select_default_account)
    build_data = staticmethod(build_data)
