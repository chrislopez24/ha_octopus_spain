#!/usr/bin/env python3
"""Safe smoke test for the Octopus Energy Spain GraphQL API.

Reads credentials from .env and prints only redacted operational status.
Never prints email, password, token, account number, CUPS, address, invoice
amounts or signed invoice URLs.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from typing import Any

import aiohttp

ROOT = Path(__file__).resolve().parents[1]
GRAPHQL_ENDPOINT = "https://api.oees-kraken.energy/v1/graphql/"

AUTH_MUTATION = """
mutation obtainKrakenToken($input: ObtainJSONWebTokenInput!) {
  obtainKrakenToken(input: $input) {
    token
  }
}
"""

VIEWER_ACCOUNT_QUERY = """
query ViewerAccount {
  viewer {
    accounts {
      ... on Account {
        number
        createdAt
        accountType
        ledgers {
          ledgerType
          balance
          number
        }
      }
    }
  }
}
"""

VIEWER_PROPERTY_QUERY = """
query ViewerProperty {
  viewer {
    accounts {
      ... on Account {
        number
        properties {
          id
          electricitySupplyPoints {
            status
            activeAgreement {
              id
              product {
                code
                atr
              }
            }
          }
        }
      }
    }
  }
}
"""

AGREEMENT_QUERY = """
query Agreement($id: ID!) {
  agreement(id: $id) {
    id
    validFrom
    validTo
    product {
      displayName
      code
      prices {
        fixedTerm
        variableTerm
        fixedTermUnits
        variableTermUnits
        dailyFee
        dailyFeeWithTaxes
        surplusRate
      }
      params
    }
  }
}
"""

BILLING_INFO_QUERY = """
query BillingInfo($accountNumber: String!) {
  accountBillingInfo(accountNumber: $accountNumber) {
    ledgers {
      ledgerType
      balance
      statementsWithDetails(first: 1) {
        edges {
          node {
            amount
            consumptionStartDate
            consumptionEndDate
            issuedDate
          }
        }
      }
    }
  }
}
"""

BILLS_QUERY = """
query Bills($accountNumber: String!, $ledgerNumber: String!, $first: Int!, $after: String) {
  account(accountNumber: $accountNumber) {
    ledgers(ledgerNumber: $ledgerNumber) {
      number
      ledgerType
      supportsInvoices
      invoices(first: $first, after: $after, orderBy: FINALIZED_AT_DESC) {
        edges {
          node {
            id
            number
            pdfUrl
            consumptionStartDate: earliestChargeAt
            consumptionEndDate: latestChargeAt
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
  }
}
"""

CREDITS_QUERY = """
query AccountCreditsQuery($accountNumber: String!, $ledgerNumber: String, $after: String) {
  account(accountNumber: $accountNumber) {
    ledgers(ledgerNumber: $ledgerNumber) {
      transactions(fromDate: "2025-01-01", first: 100, after: $after) {
        pageInfo {
          hasNextPage
          endCursor
        }
        edges {
          node {
            __typename
            ... on Credit {
              id
              amounts {
                gross
              }
              createdAt
              reasonCode
            }
          }
        }
      }
    }
  }
}
"""


class SmokeError(Exception):
    """Safe smoke-test error."""


def sanitize_message(message: str, variables: dict[str, Any] | None = None) -> str:
    """Return a diagnostic message with sensitive values redacted."""

    safe = message
    for value in _iter_string_values(variables or {}):
        if value:
            safe = safe.replace(value, "<redacted>")
    safe = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "<redacted-email>", safe)
    safe = re.sub(r"ES\d{16}[A-Z]{2}", "<redacted-cups>", safe)
    safe = re.sub(r"\bA-[A-Z0-9]+\b", "<redacted-account>", safe)
    safe = re.sub(r"\bL-[A-Z0-9]+\b", "<redacted-ledger>", safe)
    safe = re.sub(r"https://\S+X-Amz-\S+", "<redacted-signed-url>", safe)
    safe = re.sub(r"Bearer\s+\S+", "<redacted-token>", safe)
    return safe[:240]


def _iter_string_values(value: Any):
    """Yield string leaves from nested variables for message redaction."""

    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for nested in value.values():
            yield from _iter_string_values(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _iter_string_values(nested)


@dataclass(slots=True)
class Selection:
    """Sensitive selection plus safe hashes."""

    account_number: str
    property_id: str | None
    ledger_number: str | None
    agreement_id: str | None
    account_hash: str
    property_hash: str


def load_env(path: Path) -> dict[str, str]:
    """Load a minimal KEY=VALUE .env file without external dependencies."""

    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def require_credentials(values: dict[str, str]) -> tuple[str, str]:
    """Return credentials or exit with a safe message."""

    email = values.get("OCTOPUS_EMAIL", "")
    password = values.get("OCTOPUS_PASSWORD", "")
    if not email or not password:
        raise SystemExit("Rellena OCTOPUS_EMAIL y OCTOPUS_PASSWORD en .env antes de ejecutar el smoke test.")
    return email, password


def stable_hash(value: str | None) -> str:
    """Return a short stable hash for sensitive identifiers."""

    if not value:
        return "unknown"
    return sha256(value.encode("utf-8")).hexdigest()[:12]


def amount_present(value: Any) -> bool:
    """Return whether a monetary/number-like value exists without printing it."""

    if value is None:
        return False
    if isinstance(value, int | float):
        return True
    if isinstance(value, dict):
        return any(amount_present(value.get(key)) for key in ("amount", "gross", "value"))
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


def print_status(label: str, status: str, details: Any = "") -> None:
    """Print a short safe status line."""

    suffix = f" {details}" if details != "" else ""
    print(f"{label}: {status}{suffix}")


async def graphql(
    session: aiohttp.ClientSession,
    operation_name: str,
    query: str,
    variables: dict[str, Any],
    token: str | None = None,
) -> dict[str, Any]:
    """Run one GraphQL request and return JSON without logging payloads."""

    headers = {"content-type": "application/json"}
    if token:
        headers["authorization"] = token
    payload = {"operationName": operation_name, "query": query, "variables": variables}
    try:
        async with session.post(GRAPHQL_ENDPOINT, headers=headers, json=payload, timeout=30) as response:
            if response.status in (401, 403):
                raise SmokeError("authentication_failed")
            if response.status >= 400:
                raise SmokeError(f"http_{response.status}")
            data = await response.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as err:
        raise SmokeError(err.__class__.__name__) from err
    errors = data.get("errors") or []
    if errors:
        first_error = errors[0] if isinstance(errors[0], dict) else {}
        first = first_error.get("message", "graphql_error")
        code = (first_error.get("extensions") or {}).get("code", "no_code")
        category = "authentication_failed" if any(word in first.lower() for word in ("auth", "token", "permission")) else "graphql_error"
        safe_message = sanitize_message(first, variables)
        raise SmokeError(f"{operation_name}:{category}:{code}:{safe_message}")
    return data


async def login(session: aiohttp.ClientSession, email: str, password: str) -> str:
    """Authenticate and return token without printing it."""

    data = await graphql(
        session,
        "obtainKrakenToken",
        AUTH_MUTATION,
        {"input": {"email": email, "password": password}},
    )
    token = ((data.get("data") or {}).get("obtainKrakenToken") or {}).get("token")
    if not token:
        raise SmokeError("missing_token")
    return token


def select_default(account_data: dict[str, Any], property_data: dict[str, Any]) -> Selection:
    """Select first usable account/property without printing sensitive IDs."""

    accounts = (((account_data.get("data") or {}).get("viewer") or {}).get("accounts")) or []
    property_accounts = (((property_data.get("data") or {}).get("viewer") or {}).get("accounts")) or []
    properties_by_account = {account.get("number"): account.get("properties") or [] for account in property_accounts}
    if not accounts:
        raise SmokeError("no_accounts")
    account = accounts[0]
    account_number = account.get("number")
    ledgers = account.get("ledgers") or []
    electricity_ledger = next(
        (ledger for ledger in ledgers if ledger.get("ledgerType") == "SPAIN_ELECTRICITY_LEDGER"),
        ledgers[0] if ledgers else {},
    )
    property_id = None
    agreement_id = None
    for prop in properties_by_account.get(account_number, []):
        property_id = prop.get("id") or property_id
        active_supply = next(
            (sp for sp in prop.get("electricitySupplyPoints") or [] if sp.get("activeAgreement")),
            None,
        )
        if active_supply:
            agreement_id = (active_supply.get("activeAgreement") or {}).get("id")
            break
    return Selection(
        account_number=account_number,
        property_id=property_id,
        ledger_number=electricity_ledger.get("number"),
        agreement_id=agreement_id,
        account_hash=stable_hash(account_number),
        property_hash=stable_hash(property_id),
    )


def first_statement(billing: dict[str, Any]) -> dict[str, Any]:
    """Return first statement node if present."""

    ledgers = ((billing.get("data") or {}).get("accountBillingInfo") or {}).get("ledgers") or []
    ledger = next(
        (item for item in ledgers if item.get("ledgerType") == "SPAIN_ELECTRICITY_LEDGER"),
        ledgers[0] if ledgers else {},
    )
    edges = ((ledger.get("statementsWithDetails") or {}).get("edges")) or []
    return (edges[0].get("node") or {}) if edges else {}


def count_invoices(bills: dict[str, Any]) -> tuple[int, int]:
    """Return invoice count and document-available count without exposing URLs."""

    ledgers = (((bills.get("data") or {}).get("account") or {}).get("ledgers")) or []
    if not ledgers:
        return 0, 0
    edges = ((ledgers[0].get("invoices") or {}).get("edges")) or []
    document_count = sum(1 for edge in edges if (edge.get("node") or {}).get("pdfUrl"))
    return len(edges), document_count


def count_credits(credits: dict[str, Any]) -> int:
    """Return number of credit transactions without exposing values."""

    ledgers = (((credits.get("data") or {}).get("account") or {}).get("ledgers")) or []
    if not ledgers:
        return 0
    edges = ((ledgers[0].get("transactions") or {}).get("edges")) or []
    return sum(1 for edge in edges if (edge.get("node") or {}).get("__typename") == "Credit")


async def main() -> int:
    """Run a safe end-to-end API smoke test."""

    email, password = require_credentials(load_env(ROOT / ".env"))
    async with aiohttp.ClientSession() as session:
        try:
            token = await login(session, email, password)
            print_status("login", "ok")

            account_data = await graphql(session, "ViewerAccount", VIEWER_ACCOUNT_QUERY, {}, token)
            property_data = await graphql(session, "ViewerProperty", VIEWER_PROPERTY_QUERY, {}, token)
            selection = select_default(account_data, property_data)
            print_status("account_hash", "ok", selection.account_hash)
            print_status("property_hash", "ok", selection.property_hash)
            print_status("ledger", "present" if selection.ledger_number else "missing")
            print_status("agreement", "present" if selection.agreement_id else "missing")

            agreement = await graphql(session, "Agreement", AGREEMENT_QUERY, {"id": selection.agreement_id}, token) if selection.agreement_id else {}
            product = ((agreement.get("data") or {}).get("agreement") or {}).get("product") or {}
            prices = product.get("prices") or {}
            variable_terms = prices.get("variableTerm") or []
            print_status("tariff_name", "present" if product.get("displayName") else "missing")
            print_status("tariff_code", "present" if product.get("code") else "missing")
            print_status("base_energy_price", "present" if variable_terms else "missing")

            billing = await graphql(session, "BillingInfo", BILLING_INFO_QUERY, {"accountNumber": selection.account_number}, token)
            statement = first_statement(billing)
            print_status("last_invoice_amount", "present" if amount_present(statement.get("amount")) else "missing")
            print_status("last_invoice_issued", "present" if statement.get("issuedDate") else "missing")

            if selection.ledger_number:
                bills = await graphql(
                    session,
                    "Bills",
                    BILLS_QUERY,
                    {"accountNumber": selection.account_number, "ledgerNumber": selection.ledger_number, "first": 3, "after": None},
                    token,
                )
                invoice_count, document_count = count_invoices(bills)
                print_status("recent_invoices", "count", invoice_count)
                print_status("invoice_documents", "count", document_count)

                credits = await graphql(
                    session,
                    "AccountCreditsQuery",
                    CREDITS_QUERY,
                    {"accountNumber": selection.account_number, "ledgerNumber": selection.ledger_number, "after": None},
                    token,
                )
                print_status("credit_transactions", "count", count_credits(credits))
        except SmokeError as err:
            print_status("api", "failed", err)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
