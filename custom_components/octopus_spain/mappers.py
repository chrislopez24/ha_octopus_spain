"""Pure response mappers for Octopus Energy Spain."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .measurements import measurement_graph_series, measurement_period_series, measurement_rollups
from .model import AccountSelection, OctopusData
from .redaction import stable_hash


def first_edge_node(connection: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return first node from a GraphQL connection."""

    edges = (connection or {}).get("edges") or []
    if not edges:
        return None
    node = edges[0].get("node")
    return node if isinstance(node, dict) else None


def amount_value(value: Any) -> float | None:
    """Parse numeric values returned by Kraken."""

    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, dict):
        for key in ("amount", "gross", "value"):
            if key in value:
                return amount_value(value[key])
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def date_only(value: str | None) -> str | None:
    """Return date component from an ISO date/datetime string."""

    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return value[:10]


def account_selections(
    account_data: dict[str, Any], property_data: dict[str, Any]
) -> list[AccountSelection]:
    """Return every usable electricity account/property selection."""

    accounts = (((account_data.get("data") or {}).get("viewer") or {}).get("accounts")) or []
    properties_by_account = {
        account.get("number"): account.get("properties") or []
        for account in (((property_data.get("data") or {}).get("viewer") or {}).get("accounts")) or []
    }
    selections: list[AccountSelection] = []
    for account in accounts:
        account_number = account.get("number")
        ledger = electricity_ledger(account.get("ledgers") or [])
        if not account_number or not ledger.get("number"):
            continue
        for prop in properties_by_account.get(account_number, []):
            active_supply = next(
                (
                    supply
                    for supply in prop.get("electricitySupplyPoints") or []
                    if supply.get("activeAgreement")
                ),
                None,
            )
            agreement_id = ((active_supply or {}).get("activeAgreement") or {}).get("id")
            property_id = prop.get("id")
            if not property_id or not agreement_id:
                continue
            selections.append(
                AccountSelection(
                    account_number=account_number,
                    property_id=property_id,
                    ledger_number=ledger.get("number"),
                    agreement_id=agreement_id,
                    account_hash=stable_hash(account_number),
                    property_hash=stable_hash(property_id),
                )
            )
    return selections


def select_default_account(account_data: dict[str, Any], property_data: dict[str, Any]) -> AccountSelection:
    """Choose an account only when the electricity selection is unambiguous."""

    selections = account_selections(account_data, property_data)
    if not selections:
        raise ValueError("No usable Octopus electricity accounts were returned")
    if len(selections) > 1:
        raise ValueError("Multiple usable Octopus electricity accounts were returned")
    return selections[0]


def selection_from_account(
    account: dict[str, Any], properties_by_account: dict[str, list[dict[str, Any]]]
) -> AccountSelection:
    """Build AccountSelection from account/property payloads."""

    account_number = account.get("number")
    ledger = electricity_ledger(account.get("ledgers") or [])
    property_id, agreement_id = electricity_property(properties_by_account.get(account_number, []))
    return AccountSelection(
        account_number=account_number,
        property_id=property_id,
        ledger_number=ledger.get("number"),
        agreement_id=agreement_id,
        account_hash=stable_hash(account_number),
        property_hash=stable_hash(property_id),
    )


def electricity_ledger(ledgers: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the electricity ledger, falling back to first ledger."""

    return next(
        (ledger for ledger in ledgers if ledger.get("ledgerType") == "SPAIN_ELECTRICITY_LEDGER"),
        ledgers[0] if ledgers else {},
    )


def electricity_property(properties: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    """Return selected property id and active electricity agreement id."""

    selected_property_id = None
    agreement_id = None
    for prop in properties:
        selected_property_id = prop.get("id") or selected_property_id
        active_supply = next((sp for sp in prop.get("electricitySupplyPoints") or [] if sp.get("activeAgreement")), None)
        if active_supply:
            agreement_id = (active_supply.get("activeAgreement") or {}).get("id")
            break
    return selected_property_id, agreement_id


def summarize_viewer(payload: dict[str, Any]) -> dict[str, Any]:
    """Summarize safe viewer/dashboard data."""

    viewer = (payload.get("data") or {}).get("viewer") or {}
    accounts = viewer.get("accounts") or []
    properties = [prop for account in accounts for prop in account.get("properties") or []]
    electricity = [sp for prop in properties for sp in prop.get("electricitySupplyPoints") or []]
    gas = [sp for prop in properties for sp in prop.get("gasSupplyPoints") or []]
    return {
        "accounts_count": len(accounts),
        "properties_count": len(properties),
        "electricity_supply_points_count": len(electricity),
        "gas_supply_points_count": len(gas),
        "offer_messages_opted_in": (viewer.get("preferences") or {}).get("isOptedInToOfferMessages"),
        "electricity_statuses": sorted({sp.get("status") for sp in electricity if sp.get("status")}),
        "gas_statuses": sorted({sp.get("status") for sp in gas if sp.get("status")}),
        "self_consumption_present": any(sp.get("selfConsumptionCode") for sp in electricity),
    }


def summarize_linked_supply(payload: dict[str, Any]) -> dict[str, Any]:
    """Summarize linked supply point counts."""

    accounts = (((payload.get("data") or {}).get("viewer") or {}).get("accounts")) or []
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
    return {"electricity_supply_point_ids_count": electricity_count, "gas_supply_point_ids_count": gas_count}


def summarize_devices(payload: dict[str, Any]) -> dict[str, Any]:
    """Summarize devices without exposing IDs."""

    devices = (payload.get("data") or {}).get("devices") or []
    return {
        "count": len(devices),
        "device_types": sorted({item.get("deviceType") for item in devices if item.get("deviceType")}),
        "statuses": sorted({(item.get("status") or {}).get("current") for item in devices if (item.get("status") or {}).get("current")}),
    }


def summarize_solar_wallet(payload: dict[str, Any]) -> dict[str, Any]:
    """Map Solar Wallet account fields without exposing target ledgers."""

    account = ((payload.get("data") or {}).get("account")) or {}
    solar_ledgers = [
        ledger
        for ledger in account.get("ledgers") or []
        if ledger.get("ledgerType") == "SOLAR_WALLET_LEDGER"
    ]
    relationships = [
        target
        for ledger in solar_ledgers
        for target in ((ledger.get("creditTransferPermissionsData") or {}).get("toTargetLedgers") or [])
    ]
    balance = first_credit_amount(solar_ledgers, "balance")
    return {
        "has_solar_wallet": bool(solar_ledgers),
        "available_credit_eur": balance,
        "credit_left_eur": balance,
        "relationships_count": len(relationships),
        "relationships": [
            {
                "target_ledger_hash": stable_hash(item.get("ledgerNumber")),
                "target_account_hash": stable_hash(item.get("accountNumber")),
                "valid_from": item.get("validFrom"),
                "valid_to": item.get("validTo"),
            }
            for item in relationships
        ],
    }


def summarize_intelligent_go(
    payload: dict[str, Any], dispatches_payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Map modern devices and dispatches without exposing device IDs."""

    data = payload.get("data") or {}
    devices = data.get("devices") or []
    device = devices[0] if devices else {}
    status = device.get("status") or {}
    dispatches = ((dispatches_payload or {}).get("data") or {}).get("flexPlannedDispatches") or []
    return {
        "eligible_device_types": data.get("eligibleDeviceTypes") or [],
        "registered_device": {
            "present": bool(device),
            "device_type": device.get("deviceType"),
            "provider": device.get("provider"),
            "name_present": bool(device.get("name")),
            "property_hash": stable_hash(device.get("propertyId")),
            "status": status.get("current"),
            "suspended": status.get("isSuspended"),
            "state": status.get("currentState"),
        },
        "registered_devices_count": len(devices),
        "planned_dispatches": [
            {
                "start": item.get("start"),
                "end": item.get("end"),
                "type": item.get("type"),
                "energy_added_kwh": amount_value(item.get("energyAddedKwh")),
            }
            for item in dispatches
        ],
    }


def listify(value: Any) -> list[Any]:
    """Return GraphQL object-or-list values as a list."""

    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def summarize_referrals(payload: dict[str, Any]) -> dict[str, Any]:
    """Summarize referrals without exposing names or URLs."""

    account = ((payload.get("data") or {}).get("account")) or {}
    referrals = account.get("referrals") or {}
    schemes = account.get("activeReferralSchemes") or {}
    return {
        "total_count": referrals.get("totalCount"),
        "edge_count": referrals.get("edgeCount"),
        "has_next_page": (referrals.get("pageInfo") or {}).get("hasNextPage"),
        "has_previous_page": (referrals.get("pageInfo") or {}).get("hasPreviousPage"),
        "referral_url_available": bool((schemes.get("domestic") or {}).get("referralUrl")),
    }


def summarize_credits(payload: dict[str, Any]) -> dict[str, Any]:
    """Summarize credit transactions and reason codes."""

    ledgers = (((payload.get("data") or {}).get("account") or {}).get("ledgers")) or []
    credits = []
    reason_counts: dict[str, int] = {}
    reason_amounts: dict[str, float] = {}
    for edge in ((((ledgers[0] if ledgers else {}).get("transactions") or {}).get("edges")) or []):
        node = edge.get("node") or {}
        if node.get("__typename") != "Credit":
            continue
        reason = node.get("reasonCode") or "unknown"
        amount = credit_amount_eur((node.get("amounts") or {}).get("gross"))
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        if amount is not None:
            reason_amounts[reason] = reason_amounts.get(reason, 0.0) + amount
        credits.append({"amount": amount, "created_at": date_only(node.get("createdAt")), "reason_code": reason})
    connection = ((ledgers[0] if ledgers else {}).get("transactions") or {})
    return {
        "count": len(credits),
        "truncated": bool(connection.get("truncated")),
        "reason_code_counts": reason_counts,
        "reason_code_amounts": {key: round(value, 6) for key, value in sorted(reason_amounts.items())},
        "recent_credits": credits[:12],
    }


def minor_amount_eur(value: Any) -> float | None:
    """Convert a Kraken monetary amount from minor units to EUR."""

    parsed = amount_value(value)
    return round(parsed / 100, 6) if parsed is not None else None


def credit_amount_eur(value: Any) -> float | None:
    """Return credit amount in EUR from Kraken minor-unit gross values."""

    return minor_amount_eur(value)


def first_credit_amount(items: list[dict[str, Any]], key: str) -> float | None:
    """Return the first present minor-unit credit amount as EUR."""

    for item in items:
        parsed = credit_amount_eur(item.get(key))
        if parsed is not None:
            return parsed
    return None


def summarize_measurements(payload: dict[str, Any]) -> dict[str, Any]:
    """Summarize measurement connection into points and totals."""

    connection = (((payload.get("data") or {}).get("property") or {}).get("measurements") or {})
    edges = connection.get("edges") or []
    points = [measurement_point(edge.get("node") or {}) for edge in edges]
    return measurement_totals(
        [point for point in points if point],
        total_count=connection.get("totalCount"),
        truncated=bool(connection.get("truncated")),
    )


def measurement_point(node: dict[str, Any]) -> dict[str, Any] | None:
    """Map one measurement node to a safe point."""

    value = amount_value(node.get("value"))
    if value is None:
        return None
    stats = ((node.get("metaData") or {}).get("statistics")) or []
    return {
        "start_at": node.get("startAt"),
        "end_at": node.get("endAt"),
        "value": value,
        "unit": node.get("unit"),
        "cost_incl_tax": measurement_cost(stats, "costInclTax"),
        "cost_excl_tax": measurement_cost(stats, "costExclTax"),
    }


def measurement_cost(stats: list[dict[str, Any]], key: str) -> float | None:
    """Return first estimated cost from measurement statistics."""

    for stat in stats:
        cost = amount_value((stat.get(key) or {}).get("estimatedAmount"))
        if cost is not None:
            return cost
    return None


def measurement_totals(
    points: list[dict[str, Any]], *, total_count: int | None = None, truncated: bool = False
) -> dict[str, Any]:
    """Return graph-ready measurement values and rolling summaries."""

    daily_rollups = measurement_rollups(points, complete_daily_only=True)
    fallback_rollups = measurement_rollups(points, bucket_same_day=True)
    rollups = daily_rollups if daily_rollups["points_count"] else fallback_rollups
    series = measurement_graph_series(points, complete_daily_only=bool(daily_rollups["points_count"]))
    period_series = measurement_period_series(points)
    api_cost = rollups["last_365_days_cost_eur"]
    return {
        "points": points,
        "series": series,
        "period_series": period_series,
        "points_count": rollups["points_count"],
        "total_count": total_count,
        "truncated": truncated,
        "complete_daily_points_count": daily_rollups["points_count"],
        "total_consumption_kwh": rollups["last_365_days_consumption_kwh"],
        "total_cost_eur": api_cost,
        "api_cost_available": api_cost is not None,
        **rollups,
    }


def build_data(
    selection: AccountSelection,
    agreement_payload: dict[str, Any],
    billing_payload: dict[str, Any],
    invoices: list[dict[str, Any]],
    credits: dict[str, Any],
    measurements: dict[str, Any] | None = None,
    solar_wallet: dict[str, Any] | None = None,
    intelligent_go: dict[str, Any] | None = None,
) -> OctopusData:
    """Convert raw GraphQL payloads to redacted coordinator data."""

    agreement = ((agreement_payload.get("data") or {}).get("agreement")) or {}
    billing_ledgers = ((billing_payload.get("data") or {}).get("accountBillingInfo") or {}).get("ledgers") or []
    product = agreement.get("product") or {}
    prices = product.get("prices") or {}
    variable_terms = prices.get("variableTerm") or []
    fixed_terms = prices.get("fixedTerm") or []
    electricity_billing = electricity_ledger(billing_ledgers)
    last_statement = first_edge_node(electricity_billing.get("statementsWithDetails")) or {}
    return OctopusData(
        account_hash=selection.account_hash,
        property_hash=selection.property_hash,
        tariff=tariff_data(product, agreement, prices, variable_terms, fixed_terms),
        billing=billing_data(last_statement, invoices),
        invoices=invoices,
        balances={"credit_balance": minor_amount_eur(electricity_billing.get("balance"))},
        credits=credits,
        measurements=measurements or {},
        solar_wallet=solar_wallet or {},
        intelligent_go=intelligent_go or {},
    )


def tariff_data(
    product: dict[str, Any], agreement: dict[str, Any], prices: dict[str, Any], variable_terms: list[Any], fixed_terms: list[Any]
) -> dict[str, Any]:
    """Map tariff/agreement data while preserving every price term."""

    variable_prices = [amount_value(value) for value in variable_terms]
    variable_prices_with_taxes = [amount_value(value) for value in prices.get("variableTermWithTaxes") or []]
    fixed_prices = [amount_value(value) for value in fixed_terms]
    fixed_prices_with_taxes = [amount_value(value) for value in prices.get("fixedTermWithTaxes") or []]
    period_prices = spanish_period_prices(variable_prices)
    period_prices_with_taxes = spanish_period_prices(variable_prices_with_taxes)
    code = str(product.get("code") or "")
    params = product.get("params")
    product_params = parse_product_params(params)
    sun_club = sun_club_included(code, product_params)
    return {
        "name": product.get("displayName"),
        "code": product.get("code"),
        "valid_to": date_only(agreement.get("validTo")),
        "base_energy_price": variable_prices[0] if variable_prices else None,
        "base_energy_price_with_taxes": variable_prices_with_taxes[0] if variable_prices_with_taxes else None,
        "variable_prices": variable_prices,
        "variable_prices_with_taxes": variable_prices_with_taxes,
        "period_prices": period_prices,
        "period_prices_with_taxes": period_prices_with_taxes,
        "fixed_prices": fixed_prices,
        "fixed_prices_with_taxes": fixed_prices_with_taxes,
        "power_price_period_1": fixed_prices[0] if fixed_prices else None,
        "power_price_period_2": fixed_prices[1] if len(fixed_prices) > 1 else None,
        "surplus_rate": amount_value(prices.get("surplusRate")),
        "sun_club_enabled": sun_club,
        "prices_include_taxes": bool(variable_prices_with_taxes),
        "variable_term_units": prices.get("variableTermUnits"),
        "fixed_term_units": prices.get("fixedTermUnits"),
    }


def spanish_period_prices(values: list[float | None]) -> dict[str, float]:
    """Associate API's P1/P2/P3 sequence with Punta/Llano/Valle."""

    if len(values) == 1 and values[0] is not None:
        return {period: values[0] for period in ("punta", "llano", "valle")}
    names = ("punta", "llano", "valle")
    return {name: value for name, value in zip(names, values) if value is not None}


def parse_product_params(value: Any) -> dict[str, Any]:
    """Parse the JSONString product parameters without failing the mapper."""

    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        parsed: dict[str, Any] = {}
        for item in value:
            if isinstance(item, dict):
                parsed.update(item)
        return parsed
    if isinstance(value, str):
        import json

        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return decoded if isinstance(decoded, dict) else {}
    return {}


def sun_club_included(product_code: str, params: dict[str, Any]) -> bool:
    """Return true only when the active product identifies Sun Club."""

    normalized_code = product_code.lower().replace("_", "").replace("-", "")
    if "sunclub" in normalized_code:
        return True
    return any(
        params.get(key) is True
        for key in ("has_sun_club", "is_sun_club", "sun_club_enabled")
    )


def billing_data(
    last_statement: dict[str, Any], invoices: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Map latest invoice, preferring the modern invoice connection."""

    latest = next(
        (invoice for invoice in invoices or [] if not invoice.get("annulled")),
        {},
    )
    if latest:
        return {
            "last_invoice_amount": latest.get("amount_eur"),
            "last_invoice_issued": latest.get("issued_date"),
            "last_invoice_period_start": latest.get("period_start"),
            "last_invoice_period_end": latest.get("period_end"),
        }
    return {
        "last_invoice_amount": minor_amount_eur(last_statement.get("amount")),
        "last_invoice_issued": date_only(last_statement.get("issuedDate")),
        "last_invoice_period_start": date_only(last_statement.get("consumptionStartDate")),
        "last_invoice_period_end": date_only(last_statement.get("consumptionEndDate")),
    }
