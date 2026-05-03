#!/usr/bin/env python3
"""Probe all Octopus Spain GraphQL operations needed by the HA integration.

Reads .env credentials. Writes a redacted JSON report to docs/. The report must
not contain credentials, account numbers, CUPS, addresses, invoice amounts,
transaction amounts, tokens, cookies, or signed URLs.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from typing import Any

import aiohttp

sys.path.insert(0, str(Path(__file__).resolve().parent))

from smoke_test_api import (
    AGREEMENT_QUERY,
    BILLING_INFO_QUERY,
    BILLS_QUERY,
    CREDITS_QUERY,
    GRAPHQL_ENDPOINT,
    VIEWER_ACCOUNT_QUERY,
    VIEWER_PROPERTY_QUERY,
    count_credits,
    count_invoices,
    first_statement,
    load_env,
    login,
    require_credentials,
    select_default,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "docs" / "octopus-spain-api-probe-results.json"

VIEWER_SAFE_QUERY = """
query Viewer {
  viewer {
    preferences {
      isOptedInToOfferMessages
    }
    accounts {
      ... on Account {
        createdAt
        accountType
        properties {
          id
          electricitySupplyPoints {
            status
            selfConsumptionCode
          }
          gasSupplyPoints {
            status
          }
        }
      }
    }
  }
}
"""

LINKED_SUPPLY_SAFE_QUERY = """
query LinkedSupplyPointAccounts {
  viewer {
    accounts {
      ... on Account {
        properties {
          electricitySupplyPoints {
            id
          }
          gasSupplyPoints {
            id
          }
        }
      }
    }
  }
}
"""

DEVICES_QUERY = """
query getDevices($accountNumber: String!) {
  devices(accountNumber: $accountNumber) {
    deviceType
    status {
      current
    }
  }
}
"""

REFERRALS_SAFE_QUERY = """
query AccountReferrals($accountNumber: String!, $before: String, $after: String, $first: Int, $status: ReferralStatus) {
  account(accountNumber: $accountNumber) {
    referrals(before: $before, after: $after, first: $first, status: $status) {
      edgeCount
      pageInfo {
        hasNextPage
        hasPreviousPage
        startCursor
        endCursor
      }
      totalCount
    }
    activeReferralSchemes {
      domestic {
        referralUrl
      }
    }
  }
}
"""

MEASUREMENTS_QUERY = """
query getAccountMeasurements(
  $propertyId: ID!
  $first: Int!
  $utilityFilters: [UtilityFiltersInput!]
  $startOn: Date
  $endOn: Date
  $startAt: DateTime
  $endAt: DateTime
  $timezone: String
) {
  property(id: $propertyId) {
    measurements(
      first: $first
      utilityFilters: $utilityFilters
      startOn: $startOn
      endOn: $endOn
      startAt: $startAt
      endAt: $endAt
      timezone: $timezone
    ) {
      edges {
        node {
          value
          unit
          ... on IntervalMeasurementType {
            startAt
            endAt
            durationInSeconds
          }
          metaData {
            statistics {
              costExclTax {
                pricePerUnit {
                  amount
                }
                costCurrency
                estimatedAmount
              }
              costInclTax {
                costCurrency
                estimatedAmount
              }
              value
              description
              label
              type
            }
          }
        }
      }
    }
  }
}
"""

BILL_QUERY = """
query Bill($accountNumber: String!, $ledgerNumber: String!, $statementId: Int!, $after: String) {
  account(accountNumber: $accountNumber) {
    ledgers(ledgerNumber: $ledgerNumber) {
      number
      ledgerType
      supportsInvoices
      statements(first: 1, after: $after, statementId: $statementId) {
        edges {
          node {
            id
            pdfUrl
          }
        }
      }
      invoices(first: 1, after: $after, invoiceId: $statementId) {
        edges {
          node {
            id
            pdfUrl
          }
        }
      }
    }
  }
}
"""


def iso_z(dt: datetime) -> str:
    """Return ISO datetime with Z suffix."""

    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def operation_result(status: str, **extra: Any) -> dict[str, Any]:
    """Build a redacted operation result."""

    return {"status": status, **extra}


async def raw_graphql(
    session: aiohttp.ClientSession,
    token: str,
    operation_name: str,
    query: str,
    variables: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Return data or a safe error object."""

    headers = {"content-type": "application/json", "authorization": token}
    payload = {"operationName": operation_name, "query": query, "variables": variables}
    try:
        async with session.post(GRAPHQL_ENDPOINT, json=payload, headers=headers, timeout=30) as response:
            text = await response.text()
            try:
                body = json.loads(text) if text else {}
            except json.JSONDecodeError:
                body = {}
            if response.status >= 400:
                return None, {"kind": "http", "status": response.status}
    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
        return None, {"kind": "transport", "class": err.__class__.__name__}
    errors = body.get("errors") or []
    if errors:
        first = errors[0] if isinstance(errors[0], dict) else {}
        return None, {
            "kind": "graphql",
            "code": (first.get("extensions") or {}).get("code"),
            "message_class": classify_message(str(first.get("message", "graphql_error"))),
        }
    return body, None


def classify_message(message: str) -> str:
    lowered = message.lower()
    if "auth" in lowered or "token" in lowered or "permission" in lowered:
        return "authentication_or_permission"
    if "cannot query field" in lowered:
        return "schema_field_error"
    if "invalid" in lowered:
        return "invalid_request"
    return "graphql_error"


def summarize_viewer(payload: dict[str, Any]) -> dict[str, Any]:
    viewer = (payload.get("data") or {}).get("viewer") or {}
    accounts = viewer.get("accounts") or []
    property_count = sum(len(account.get("properties") or []) for account in accounts)
    electricity_count = sum(
        len(prop.get("electricitySupplyPoints") or [])
        for account in accounts
        for prop in account.get("properties") or []
    )
    gas_count = sum(
        len(prop.get("gasSupplyPoints") or [])
        for account in accounts
        for prop in account.get("properties") or []
    )
    return {
        "accounts_count": len(accounts),
        "properties_count": property_count,
        "electricity_supply_points_count": electricity_count,
        "gas_supply_points_count": gas_count,
        "preferences_present": bool(viewer.get("preferences")),
    }


def summarize_account(payload: dict[str, Any]) -> dict[str, Any]:
    accounts = (((payload.get("data") or {}).get("viewer") or {}).get("accounts")) or []
    ledgers = [ledger for account in accounts for ledger in account.get("ledgers") or []]
    return {
        "accounts_count": len(accounts),
        "ledger_types": sorted({ledger.get("ledgerType") for ledger in ledgers if ledger.get("ledgerType")}),
        "ledgers_count": len(ledgers),
        "balances_present": sum(1 for ledger in ledgers if ledger.get("balance") is not None),
    }


def summarize_property(payload: dict[str, Any]) -> dict[str, Any]:
    accounts = (((payload.get("data") or {}).get("viewer") or {}).get("accounts")) or []
    props = [prop for account in accounts for prop in account.get("properties") or []]
    active_agreements = sum(
        1
        for prop in props
        for sp in prop.get("electricitySupplyPoints") or []
        if sp.get("activeAgreement")
    )
    return {"properties_count": len(props), "active_electricity_agreements_count": active_agreements}


def summarize_agreement(payload: dict[str, Any]) -> dict[str, Any]:
    agreement = ((payload.get("data") or {}).get("agreement")) or {}
    product = agreement.get("product") or {}
    prices = product.get("prices") or {}
    return {
        "agreement_present": bool(agreement),
        "product_name_present": bool(product.get("displayName")),
        "product_code_present": bool(product.get("code")),
        "valid_to_present": bool(agreement.get("validTo")),
        "variable_terms_count": len(prices.get("variableTerm") or []),
        "fixed_terms_count": len(prices.get("fixedTerm") or []),
        "surplus_rate_present": prices.get("surplusRate") is not None,
    }


def summarize_billing(payload: dict[str, Any]) -> dict[str, Any]:
    info = ((payload.get("data") or {}).get("accountBillingInfo")) or {}
    ledgers = info.get("ledgers") or []
    statement = first_statement(payload)
    return {
        "ledgers_count": len(ledgers),
        "statement_edges_count": sum(len(((ledger.get("statementsWithDetails") or {}).get("edges")) or []) for ledger in ledgers),
        "last_statement_amount_present": statement.get("amount") is not None,
        "last_statement_issued_present": bool(statement.get("issuedDate")),
    }


def summarize_bills(payload: dict[str, Any]) -> dict[str, Any]:
    invoice_count, document_count = count_invoices(payload)
    ledgers = (((payload.get("data") or {}).get("account") or {}).get("ledgers")) or []
    page_info = (((ledgers[0].get("invoices") or {}).get("pageInfo")) if ledgers else {}) or {}
    return {
        "invoice_edges_count": invoice_count,
        "invoice_documents_count": document_count,
        "has_next_page": bool(page_info.get("hasNextPage")),
        "end_cursor_present": bool(page_info.get("endCursor")),
    }


def first_invoice_id(payload: dict[str, Any]) -> int | None:
    ledgers = (((payload.get("data") or {}).get("account") or {}).get("ledgers")) or []
    edges = (((ledgers[0].get("invoices") or {}).get("edges")) if ledgers else []) or []
    node = (edges[0].get("node") or {}) if edges else {}
    invoice_id = node.get("id")
    return int(invoice_id) if invoice_id is not None else None


def summarize_bill(payload: dict[str, Any]) -> dict[str, Any]:
    ledgers = (((payload.get("data") or {}).get("account") or {}).get("ledgers")) or []
    ledger = ledgers[0] if ledgers else {}
    statement_edges = ((ledger.get("statements") or {}).get("edges")) or []
    invoice_edges = ((ledger.get("invoices") or {}).get("edges")) or []
    invoice_node = (invoice_edges[0].get("node") or {}) if invoice_edges else {}
    statement_node = (statement_edges[0].get("node") or {}) if statement_edges else {}
    return {
        "statement_edges_count": len(statement_edges),
        "invoice_edges_count": len(invoice_edges),
        "pdf_url_present": bool(invoice_node.get("pdfUrl") or statement_node.get("pdfUrl")),
    }


def summarize_credits(payload: dict[str, Any]) -> dict[str, Any]:
    ledgers = (((payload.get("data") or {}).get("account") or {}).get("ledgers")) or []
    edges = ((((ledgers[0] if ledgers else {}).get("transactions") or {}).get("edges")) or [])
    reason_counts: dict[str, int] = {}
    for edge in edges:
        node = edge.get("node") or {}
        if node.get("__typename") != "Credit":
            continue
        reason = node.get("reasonCode") or "unknown"
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    return {"credit_edges_count": count_credits(payload), "reason_code_counts": reason_counts}


def summarize_devices(payload: dict[str, Any]) -> dict[str, Any]:
    devices = (payload.get("data") or {}).get("devices") or []
    return {
        "devices_count": len(devices),
        "device_types": sorted({device.get("deviceType") for device in devices if device.get("deviceType")}),
        "status_present_count": sum(1 for device in devices if (device.get("status") or {}).get("current") is not None),
    }


def summarize_referrals(payload: dict[str, Any]) -> dict[str, Any]:
    account = ((payload.get("data") or {}).get("account")) or {}
    referrals = account.get("referrals") or {}
    schemes = account.get("activeReferralSchemes") or {}
    return {
        "total_count_present": referrals.get("totalCount") is not None,
        "edge_count_present": referrals.get("edgeCount") is not None,
        "referral_url_present": bool(((schemes.get("domestic") or {}).get("referralUrl"))),
    }


def summarize_linked_supply(payload: dict[str, Any]) -> dict[str, Any]:
    accounts = (((payload.get("data") or {}).get("viewer") or {}).get("accounts")) or []
    electricity_ids = sum(
        len(prop.get("electricitySupplyPoints") or [])
        for account in accounts
        for prop in account.get("properties") or []
    )
    gas_ids = sum(
        len(prop.get("gasSupplyPoints") or [])
        for account in accounts
        for prop in account.get("properties") or []
    )
    return {"electricity_supply_point_ids_count": electricity_ids, "gas_supply_point_ids_count": gas_ids}


def summarize_measurements(payload: dict[str, Any]) -> dict[str, Any]:
    measurements = (((payload.get("data") or {}).get("property") or {}).get("measurements") or {}).get("edges") or []
    first_node = (measurements[0].get("node") or {}) if measurements else {}
    last_node = (measurements[-1].get("node") or {}) if measurements else {}
    stats = ((first_node.get("metaData") or {}).get("statistics")) or []
    units = sorted({(edge.get("node") or {}).get("unit") for edge in measurements if (edge.get("node") or {}).get("unit")})
    return {
        "edges_count": len(measurements),
        "units": units,
        "unit_present": bool(first_node.get("unit")),
        "first_interval_start_present": bool(first_node.get("startAt")),
        "last_interval_end_present": bool(last_node.get("endAt")),
        "statistics_count_first_edge": len(stats),
        "statistics_any_present": any(((edge.get("node") or {}).get("metaData") or {}).get("statistics") for edge in measurements),
        "cost_incl_tax_present": any(
            (stat.get("costInclTax") or {}).get("estimatedAmount") is not None
            for edge in measurements
            for stat in (((edge.get("node") or {}).get("metaData") or {}).get("statistics") or [])
        ),
        "cost_excl_tax_present": any(
            (stat.get("costExclTax") or {}).get("estimatedAmount") is not None
            for edge in measurements
            for stat in (((edge.get("node") or {}).get("metaData") or {}).get("statistics") or [])
        ),
    }


async def probe_operation(
    report: dict[str, Any],
    session: aiohttp.ClientSession,
    token: str,
    label: str,
    operation_name: str,
    query: str,
    variables: dict[str, Any],
    summarize,
) -> dict[str, Any] | None:
    payload, error = await raw_graphql(session, token, operation_name, query, variables)
    if error:
        report["operations"][label] = operation_result("failed", operation_name=operation_name, error=error)
        return None
    report["operations"][label] = operation_result("ok", operation_name=operation_name, **summarize(payload or {}))
    return payload


async def main() -> int:
    email, password = require_credentials(load_env(ROOT / ".env"))
    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "endpoint": GRAPHQL_ENDPOINT,
        "operations": {},
        "notes": [],
    }
    async with aiohttp.ClientSession() as session:
        try:
            token = await login(session, email, password)
        except Exception as err:
            report["operations"]["obtainKrakenToken"] = operation_result(
                "failed", error={"kind": "auth", "class": err.__class__.__name__}
            )
            REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
            return 1
        report["operations"]["obtainKrakenToken"] = operation_result("ok", token_returned=True)

        account_payload = await probe_operation(report, session, token, "ViewerAccount", "ViewerAccount", VIEWER_ACCOUNT_QUERY, {}, summarize_account)
        property_payload = await probe_operation(report, session, token, "ViewerProperty", "ViewerProperty", VIEWER_PROPERTY_QUERY, {}, summarize_property)
        await probe_operation(report, session, token, "ViewerSafe", "Viewer", VIEWER_SAFE_QUERY, {}, summarize_viewer)
        await probe_operation(report, session, token, "LinkedSupplyPointAccountsSafe", "LinkedSupplyPointAccounts", LINKED_SUPPLY_SAFE_QUERY, {}, summarize_linked_supply)

        if not account_payload or not property_payload:
            REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
            return 1

        selection = select_default(account_payload, property_payload)
        report["selection"] = {
            "account_hash": selection.account_hash,
            "property_hash": selection.property_hash,
            "ledger_present": bool(selection.ledger_number),
            "agreement_present": bool(selection.agreement_id),
        }

        if selection.agreement_id:
            await probe_operation(
                report,
                session,
                token,
                "Agreement",
                "Agreement",
                AGREEMENT_QUERY,
                {"id": selection.agreement_id},
                summarize_agreement,
            )
        if selection.account_number:
            await probe_operation(
                report,
                session,
                token,
                "BillingInfo",
                "BillingInfo",
                BILLING_INFO_QUERY,
                {"accountNumber": selection.account_number},
                summarize_billing,
            )
            await probe_operation(
                report,
                session,
                token,
                "getDevices",
                "getDevices",
                DEVICES_QUERY,
                {"accountNumber": selection.account_number},
                summarize_devices,
            )
            await probe_operation(
                report,
                session,
                token,
                "AccountReferralsSafe",
                "AccountReferrals",
                REFERRALS_SAFE_QUERY,
                {"accountNumber": selection.account_number, "first": 5, "after": None},
                summarize_referrals,
            )
        bills_payload = None
        if selection.account_number and selection.ledger_number:
            bills_payload = await probe_operation(
                report,
                session,
                token,
                "Bills",
                "Bills",
                BILLS_QUERY,
                {"accountNumber": selection.account_number, "ledgerNumber": selection.ledger_number, "first": 12, "after": None},
                summarize_bills,
            )
            await probe_operation(
                report,
                session,
                token,
                "AccountCreditsQuery",
                "AccountCreditsQuery",
                CREDITS_QUERY,
                {"accountNumber": selection.account_number, "ledgerNumber": selection.ledger_number, "after": None},
                summarize_credits,
            )
        if bills_payload and selection.account_number and selection.ledger_number:
            invoice_id = first_invoice_id(bills_payload)
            if invoice_id is not None:
                await probe_operation(
                    report,
                    session,
                    token,
                    "Bill",
                    "Bill",
                    BILL_QUERY,
                    {
                        "accountNumber": selection.account_number,
                        "ledgerNumber": selection.ledger_number,
                        "statementId": invoice_id,
                        "after": None,
                    },
                    summarize_bill,
                )

        if selection.property_id:
            now = datetime.now(timezone.utc)
            end_at = now - timedelta(days=2)
            start_at = end_at - timedelta(days=31)
            common_filter = {
                "electricityFilters": {
                    "readingDirection": "CONSUMPTION",
                    "readingFrequencyType": "DAY_INTERVAL",
                }
            }
            await probe_operation(
                report,
                session,
                token,
                "getAccountMeasurementsDailyConsumption",
                "getAccountMeasurements",
                MEASUREMENTS_QUERY,
                {
                    "propertyId": selection.property_id,
                    "first": 31,
                    "startAt": iso_z(start_at),
                    "endAt": iso_z(end_at),
                    "timezone": "Europe/Madrid",
                    "utilityFilters": [common_filter],
                },
                summarize_measurements,
            )
            hourly_filter = {
                "electricityFilters": {
                    "readingDirection": "CONSUMPTION",
                    "readingFrequencyType": "HOUR_INTERVAL",
                }
            }
            await probe_operation(
                report,
                session,
                token,
                "getAccountMeasurementsHourlyConsumption",
                "getAccountMeasurements",
                MEASUREMENTS_QUERY,
                {
                    "propertyId": selection.property_id,
                    "first": 48,
                    "startAt": iso_z(end_at - timedelta(days=2)),
                    "endAt": iso_z(end_at),
                    "timezone": "Europe/Madrid",
                    "utilityFilters": [hourly_filter],
                },
                summarize_measurements,
            )
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    for name, result in report["operations"].items():
        print(name + ":", result["status"])
    print("report:", REPORT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
