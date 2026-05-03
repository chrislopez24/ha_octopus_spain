#!/usr/bin/env python3
"""Safe smoke test for the real Octopus Spain web navigation flow.

Uses the flow observed in HAR files:
1. POST https://octopusenergy.es/api/auth/login
2. POST https://octopusenergy.es/api/graphql/kraken

The output is intentionally redacted: no credentials, cookies, token, account
number, CUPS, address, invoice amounts or signed URLs are printed.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

import aiohttp

ROOT = Path(__file__).resolve().parents[1]
LOGIN_ENDPOINT = "https://octopusenergy.es/api/auth/login"
GRAPHQL_PROXY_ENDPOINT = "https://octopusenergy.es/api/graphql/kraken"

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
    email = values.get("OCTOPUS_EMAIL", "")
    password = values.get("OCTOPUS_PASSWORD", "")
    if not email or not password:
        raise SystemExit("Rellena OCTOPUS_EMAIL y OCTOPUS_PASSWORD en .env antes de ejecutar el smoke test.")
    return email, password


def stable_hash(value: str | None) -> str:
    if not value:
        return "unknown"
    return sha256(value.encode("utf-8")).hexdigest()[:12]


def print_status(label: str, status: str, details: Any = "") -> None:
    suffix = f" {details}" if details != "" else ""
    print(f"{label}: {status}{suffix}")


def sanitize_message(message: str) -> str:
    safe = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "<redacted-email>", message)
    safe = re.sub(r"ES\d{16}[A-Z]{2}", "<redacted-cups>", safe)
    safe = re.sub(r"\bA-[A-Z0-9]+\b", "<redacted-account>", safe)
    safe = re.sub(r"\bL-[A-Z0-9]+\b", "<redacted-ledger>", safe)
    safe = re.sub(r"https://\S+X-Amz-\S+", "<redacted-signed-url>", safe)
    return safe[:240]


async def web_login(session: aiohttp.ClientSession, email: str, password: str) -> None:
    payload = {"email": email, "password": password, "nextPage": "/dashboard"}
    headers = {
        "content-type": "application/json",
        "origin": "https://octopusenergy.es",
        "referer": "https://octopusenergy.es/login",
        "user-agent": "Mozilla/5.0 HomeAssistant-OctopusSpain-SmokeTest",
    }
    try:
        async with session.post(LOGIN_ENDPOINT, json=payload, headers=headers, timeout=30) as response:
            raw_text = await response.text()
            try:
                data = json.loads(raw_text) if raw_text else {}
            except json.JSONDecodeError:
                data = {"raw": raw_text}
            if response.status >= 400:
                safe_error = sanitize_message(json.dumps(data, ensure_ascii=False) if data else raw_text)
                raise SmokeError(f"web_login_http_{response.status}:{safe_error}")
    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
        raise SmokeError(f"web_login_transport_{err.__class__.__name__}") from err
    if isinstance(data, dict):
        error = data.get("error") or data.get("message")
        if error:
            raise SmokeError(f"web_login_error:{sanitize_message(str(error))}")


async def graphql_proxy(
    session: aiohttp.ClientSession,
    operation_name: str,
    query: str,
    variables: dict[str, Any],
) -> dict[str, Any]:
    headers = {
        "content-type": "application/json",
        "origin": "https://octopusenergy.es",
        "referer": "https://octopusenergy.es/dashboard",
        "user-agent": "Mozilla/5.0 HomeAssistant-OctopusSpain-SmokeTest",
    }
    payload = {"operationName": operation_name, "query": query, "variables": variables}
    try:
        async with session.post(GRAPHQL_PROXY_ENDPOINT, json=payload, headers=headers, timeout=30) as response:
            if response.status in (401, 403):
                raise SmokeError(f"{operation_name}:auth_http_{response.status}")
            if response.status >= 400:
                raise SmokeError(f"{operation_name}:http_{response.status}")
            data = await response.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as err:
        raise SmokeError(f"{operation_name}:transport_{err.__class__.__name__}") from err
    errors = data.get("errors") or []
    if errors:
        first = errors[0].get("message", "graphql_error") if isinstance(errors[0], dict) else "graphql_error"
        raise SmokeError(f"{operation_name}:graphql_error:{sanitize_message(str(first))}")
    return data


def select_default(account_data: dict[str, Any], property_data: dict[str, Any]) -> Selection:
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
    ledgers = ((billing.get("data") or {}).get("accountBillingInfo") or {}).get("ledgers") or []
    ledger = next(
        (item for item in ledgers if item.get("ledgerType") == "SPAIN_ELECTRICITY_LEDGER"),
        ledgers[0] if ledgers else {},
    )
    edges = ((ledger.get("statementsWithDetails") or {}).get("edges")) or []
    return (edges[0].get("node") or {}) if edges else {}


def amount_present(value: Any) -> bool:
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


def count_invoices(bills: dict[str, Any]) -> tuple[int, int]:
    ledgers = (((bills.get("data") or {}).get("account") or {}).get("ledgers")) or []
    if not ledgers:
        return 0, 0
    edges = ((ledgers[0].get("invoices") or {}).get("edges")) or []
    document_count = sum(1 for edge in edges if (edge.get("node") or {}).get("pdfUrl"))
    return len(edges), document_count


def count_credits(credits: dict[str, Any]) -> int:
    ledgers = (((credits.get("data") or {}).get("account") or {}).get("ledgers")) or []
    if not ledgers:
        return 0
    edges = ((ledgers[0].get("transactions") or {}).get("edges")) or []
    return sum(1 for edge in edges if (edge.get("node") or {}).get("__typename") == "Credit")


async def main() -> int:
    email, password = require_credentials(load_env(ROOT / ".env"))
    cookie_jar = aiohttp.CookieJar(unsafe=False)
    async with aiohttp.ClientSession(cookie_jar=cookie_jar) as session:
        try:
            await web_login(session, email, password)
            print_status("web_login", "ok")
            print_status("session_cookies", "present" if len(cookie_jar) else "missing")

            account_data = await graphql_proxy(session, "ViewerAccount", VIEWER_ACCOUNT_QUERY, {})
            print_status("ViewerAccount", "ok")
            property_data = await graphql_proxy(session, "ViewerProperty", VIEWER_PROPERTY_QUERY, {})
            print_status("ViewerProperty", "ok")
            selection = select_default(account_data, property_data)
            print_status("account_hash", "ok", selection.account_hash)
            print_status("property_hash", "ok", selection.property_hash)
            print_status("ledger", "present" if selection.ledger_number else "missing")
            print_status("agreement", "present" if selection.agreement_id else "missing")

            if selection.agreement_id:
                agreement = await graphql_proxy(session, "Agreement", AGREEMENT_QUERY, {"id": selection.agreement_id})
                product = ((agreement.get("data") or {}).get("agreement") or {}).get("product") or {}
                print_status("Agreement", "ok")
                print_status("tariff_name", "present" if product.get("displayName") else "missing")
                print_status("tariff_code", "present" if product.get("code") else "missing")
            else:
                print_status("Agreement", "skipped", "missing_agreement_id")

            billing = await graphql_proxy(session, "BillingInfo", BILLING_INFO_QUERY, {"accountNumber": selection.account_number})
            statement = first_statement(billing)
            print_status("BillingInfo", "ok")
            print_status("last_invoice_amount", "present" if amount_present(statement.get("amount")) else "missing")
            print_status("last_invoice_issued", "present" if statement.get("issuedDate") else "missing")

            if selection.ledger_number:
                bills = await graphql_proxy(
                    session,
                    "Bills",
                    BILLS_QUERY,
                    {"accountNumber": selection.account_number, "ledgerNumber": selection.ledger_number, "first": 3, "after": None},
                )
                invoice_count, document_count = count_invoices(bills)
                print_status("Bills", "ok")
                print_status("recent_invoices", "count", invoice_count)
                print_status("invoice_documents", "count", document_count)

                credits = await graphql_proxy(
                    session,
                    "AccountCreditsQuery",
                    CREDITS_QUERY,
                    {"accountNumber": selection.account_number, "ledgerNumber": selection.ledger_number, "after": None},
                )
                print_status("AccountCreditsQuery", "ok")
                print_status("credit_transactions", "count", count_credits(credits))
            else:
                print_status("Bills", "skipped", "missing_ledger_number")
                print_status("AccountCreditsQuery", "skipped", "missing_ledger_number")
        except SmokeError as err:
            print_status("api", "failed", err)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
