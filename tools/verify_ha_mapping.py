#!/usr/bin/env python3
"""Verify the Home Assistant mapping coverage against live Octopus API.

This script does not import the HA custom component package because the local
environment does not include Home Assistant. It verifies the same operation set
and prints only redacted mapping status.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys

import aiohttp

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from probe_octopus_endpoints import (
    AGREEMENT_QUERY,
    BILLING_INFO_QUERY,
    BILL_QUERY,
    BILLS_QUERY,
    CREDITS_QUERY,
    DEVICES_QUERY,
    LINKED_SUPPLY_SAFE_QUERY,
    MEASUREMENTS_QUERY,
    REFERRALS_SAFE_QUERY,
    VIEWER_SAFE_QUERY,
    first_invoice_id,
    iso_z,
    summarize_agreement,
    summarize_bill,
    summarize_billing,
    summarize_bills,
    summarize_credits,
    summarize_devices,
    summarize_linked_supply,
    summarize_measurements,
    summarize_referrals,
    summarize_viewer,
)
from smoke_test_api import (
    VIEWER_ACCOUNT_QUERY,
    VIEWER_PROPERTY_QUERY,
    graphql,
    load_env,
    login,
    require_credentials,
    select_default,
)
from datetime import datetime, timedelta, timezone


async def main() -> int:
    email, password = require_credentials(load_env(Path(".env")))
    async with aiohttp.ClientSession() as session:
        token = await login(session, email, password)
        print("auth.token: mapped")

        account = await graphql(session, "ViewerAccount", VIEWER_ACCOUNT_QUERY, {}, token)
        prop = await graphql(session, "ViewerProperty", VIEWER_PROPERTY_QUERY, {}, token)
        selection = select_default(account, prop)
        print("config.account_hash: mapped", selection.account_hash)
        print("config.property_hash: mapped", selection.property_hash)
        print("config.ledger: mapped" if selection.ledger_number else "config.ledger: missing")
        print("config.agreement: mapped" if selection.agreement_id else "config.agreement: missing")

        viewer = await graphql(session, "Viewer", VIEWER_SAFE_QUERY, {}, token)
        viewer_summary = summarize_viewer(viewer)
        print("overview.viewer: mapped", viewer_summary["accounts_count"], viewer_summary["properties_count"])

        linked = await graphql(session, "LinkedSupplyPointAccounts", LINKED_SUPPLY_SAFE_QUERY, {}, token)
        linked_summary = summarize_linked_supply(linked)
        print("overview.linked_supply: mapped", linked_summary["electricity_supply_point_ids_count"])

        agreement = await graphql(session, "Agreement", AGREEMENT_QUERY, {"id": selection.agreement_id}, token)
        agreement_summary = summarize_agreement(agreement)
        print("tariff.agreement: mapped", agreement_summary["product_name_present"], agreement_summary["variable_terms_count"])

        billing = await graphql(session, "BillingInfo", BILLING_INFO_QUERY, {"accountNumber": selection.account_number}, token)
        billing_summary = summarize_billing(billing)
        print("billing.statements: mapped", billing_summary["statement_edges_count"])

        devices = await graphql(session, "getDevices", DEVICES_QUERY, {"accountNumber": selection.account_number}, token)
        devices_summary = summarize_devices(devices)
        print("devices: mapped", devices_summary["devices_count"])

        referrals = await graphql(
            session,
            "AccountReferrals",
            REFERRALS_SAFE_QUERY,
            {"accountNumber": selection.account_number, "first": 5, "after": None},
            token,
        )
        referrals_summary = summarize_referrals(referrals)
        print("referrals.safe_summary: mapped", referrals_summary["total_count_present"])

        bills = await graphql(
            session,
            "Bills",
            BILLS_QUERY,
            {"accountNumber": selection.account_number, "ledgerNumber": selection.ledger_number, "first": 12, "after": None},
            token,
        )
        bills_summary = summarize_bills(bills)
        print("invoices.list: mapped", bills_summary["invoice_edges_count"], bills_summary["invoice_documents_count"])

        invoice_id = first_invoice_id(bills)
        if invoice_id is not None:
            bill = await graphql(
                session,
                "Bill",
                BILL_QUERY,
                {"accountNumber": selection.account_number, "ledgerNumber": selection.ledger_number, "statementId": invoice_id, "after": None},
                token,
            )
            bill_summary = summarize_bill(bill)
            print("invoices.document: mapped", bill_summary["pdf_url_present"])
        else:
            print("invoices.document: skipped")

        credits = await graphql(
            session,
            "AccountCreditsQuery",
            CREDITS_QUERY,
            {"accountNumber": selection.account_number, "ledgerNumber": selection.ledger_number, "after": None},
            token,
        )
        credits_summary = summarize_credits(credits)
        print("credits.reason_codes: mapped", credits_summary["credit_edges_count"], sorted(credits_summary["reason_code_counts"].keys()))

        end_at = datetime.now(timezone.utc) - timedelta(days=2)
        daily = await graphql(
            session,
            "getAccountMeasurements",
            MEASUREMENTS_QUERY,
            {
                "propertyId": selection.property_id,
                "first": 31,
                "startAt": iso_z(end_at - timedelta(days=31)),
                "endAt": iso_z(end_at),
                "timezone": "Europe/Madrid",
                "utilityFilters": [{"electricityFilters": {"readingDirection": "CONSUMPTION", "readingFrequencyType": "DAY_INTERVAL"}}],
            },
            token,
        )
        daily_summary = summarize_measurements(daily)
        print("measurements.daily: mapped", daily_summary["edges_count"], daily_summary["units"])

        hourly = await graphql(
            session,
            "getAccountMeasurements",
            MEASUREMENTS_QUERY,
            {
                "propertyId": selection.property_id,
                "first": 48,
                "startAt": iso_z(end_at - timedelta(days=2)),
                "endAt": iso_z(end_at),
                "timezone": "Europe/Madrid",
                "utilityFilters": [{"electricityFilters": {"readingDirection": "CONSUMPTION", "readingFrequencyType": "HOUR_INTERVAL"}}],
            },
            token,
        )
        hourly_summary = summarize_measurements(hourly)
        print("measurements.hourly: mapped", hourly_summary["edges_count"], hourly_summary["units"])
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
