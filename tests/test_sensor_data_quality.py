from types import SimpleNamespace

from custom_components.octopus_spain import binary_sensor, mappers, measurements, sensor


def test_daily_rollups_ignore_partial_days_when_requested():
    points = [
        {
            "start_at": "2026-04-01T16:00:00+02:00",
            "end_at": "2026-04-02T00:00:00+02:00",
            "value": 99,
            "unit": "kwh",
            "cost_incl_tax": None,
        },
        {
            "start_at": "2026-04-02T00:00:00+02:00",
            "end_at": "2026-04-03T00:00:00+02:00",
            "value": 10,
            "unit": "kwh",
            "cost_incl_tax": None,
        },
    ]

    result = measurements.measurement_rollups(points, complete_daily_only=True)

    assert result["points_count"] == 1
    assert result["last_day_consumption_kwh"] == 10.0
    assert result["latest_period_start"] == "2026-04-02T00:00:00+02:00"
    assert result["latest_period_end"] == "2026-04-03T00:00:00+02:00"


def test_estimated_sun_club_costs_are_derived_from_hourly_consumption():
    daily_points = [
        {
            "start_at": "2026-04-01T00:00:00+02:00",
            "end_at": "2026-04-02T00:00:00+02:00",
            "value": 3,
            "unit": "kwh",
            "cost_incl_tax": None,
        }
    ]
    hourly_points = [
        {
            "start_at": "2026-04-01T11:00:00+02:00",
            "end_at": "2026-04-01T12:00:00+02:00",
            "value": 1,
            "unit": "kwh",
            "cost_incl_tax": None,
        },
        {
            "start_at": "2026-04-01T12:00:00+02:00",
            "end_at": "2026-04-01T13:00:00+02:00",
            "value": 2,
            "unit": "kwh",
            "cost_incl_tax": None,
        },
    ]

    result = measurements.estimated_energy_costs_from_hourly(
        daily_points,
        hourly_points,
        variable_prices={"punta": 0.13, "llano": 0.13, "valle": 0.13},
        sun_club_enabled=True,
        sun_club_discount=0.45,
        sun_club_start_hour=12,
        sun_club_end_hour=18,
    )

    assert result["estimated_last_day_cost_eur"] == 0.273
    assert result["estimated_last_7_days_cost_eur"] == 0.273
    assert result["estimated_last_31_days_cost_eur"] == 0.273
    assert result["estimated_cost_days_count"] == 1
    assert result["estimated_cost_source"] == "estimated_from_hourly_consumption_and_tariff"
    assert result["series_by_date"] == {"2026-04-01": 0.273}


def test_sun_club_discount_applies_only_inside_window_for_eligible_product():
    daily_points = [
        {"start_at": "2026-04-01T00:00:00+02:00", "end_at": "2026-04-02T00:00:00+02:00", "value": 2, "unit": "kwh"}
    ]
    hourly_points = [
        {"start_at": "2026-04-01T11:00:00+02:00", "end_at": "2026-04-01T12:00:00+02:00", "value": 1, "unit": "kwh"},
        {"start_at": "2026-04-01T12:00:00+02:00", "end_at": "2026-04-01T13:00:00+02:00", "value": 1, "unit": "kwh"},
    ]

    result = measurements.estimated_energy_costs_from_hourly(
        daily_points,
        hourly_points,
        variable_prices={"punta": 0.30, "llano": 0.20, "valle": 0.10},
        sun_club_enabled=True,
        sun_club_discount=0.45,
        sun_club_start_hour=12,
        sun_club_end_hour=18,
    )

    assert result["series_by_date"] == {"2026-04-01": 0.465}


def test_multiperiod_costs_use_punta_llano_and_valle_on_weekdays():
    daily_points = [
        {"start_at": "2026-04-01T00:00:00+02:00", "end_at": "2026-04-02T00:00:00+02:00", "value": 3, "unit": "kwh"}
    ]
    hourly_points = [
        {"start_at": "2026-04-01T10:00:00+02:00", "end_at": "2026-04-01T11:00:00+02:00", "value": 1, "unit": "kwh"},
        {"start_at": "2026-04-01T14:00:00+02:00", "end_at": "2026-04-01T15:00:00+02:00", "value": 1, "unit": "kwh"},
        {"start_at": "2026-04-01T03:00:00+02:00", "end_at": "2026-04-01T04:00:00+02:00", "value": 1, "unit": "kwh"},
    ]

    result = measurements.estimated_energy_costs_from_hourly(
        daily_points,
        hourly_points,
        variable_prices={"punta": 0.30, "llano": 0.20, "valle": 0.10},
        sun_club_enabled=False,
        sun_club_discount=0.45,
        sun_club_start_hour=12,
        sun_club_end_hour=18,
    )

    assert result["series_by_date"] == {"2026-04-01": 0.6}


def test_weekends_use_valle_and_non_sun_club_accounts_never_get_discount():
    daily_points = [
        {"start_at": "2026-04-04T00:00:00+02:00", "end_at": "2026-04-05T00:00:00+02:00", "value": 2, "unit": "kwh"}
    ]
    hourly_points = [
        {"start_at": "2026-04-04T10:00:00+02:00", "end_at": "2026-04-04T11:00:00+02:00", "value": 1, "unit": "kwh"},
        {"start_at": "2026-04-04T14:00:00+02:00", "end_at": "2026-04-04T15:00:00+02:00", "value": 1, "unit": "kwh"},
    ]

    result = measurements.estimated_energy_costs_from_hourly(
        daily_points,
        hourly_points,
        variable_prices={"punta": 0.30, "llano": 0.20, "valle": 0.10},
        sun_club_enabled=False,
        sun_club_discount=0.45,
        sun_club_start_hour=12,
        sun_club_end_hour=18,
    )

    assert result["series_by_date"] == {"2026-04-04": 0.2}


def test_tariff_mapper_preserves_taxed_and_untaxed_terms_and_sun_club_flag():
    tariff = mappers.tariff_data(
        {
            "code": "SUNCLUB-2026-W21",
            "params": '{"solar_product_rollover_code": "SUNCLUB-2026-W21"}',
        },
        {},
        {
            "variableTerm": [0.30, 0.20, 0.10],
            "variableTermWithTaxes": [0.36, 0.24, 0.12],
            "fixedTerm": [0.09, 0.04],
            "fixedTermWithTaxes": [0.11, 0.05],
        },
        [0.30, 0.20, 0.10],
        [0.09, 0.04],
    )

    assert tariff["period_prices"] == {"punta": 0.30, "llano": 0.20, "valle": 0.10}
    assert tariff["period_prices_with_taxes"] == {"punta": 0.36, "llano": 0.24, "valle": 0.12}
    assert tariff["fixed_prices"] == [0.09, 0.04]
    assert tariff["fixed_prices_with_taxes"] == [0.11, 0.05]
    assert tariff["sun_club_enabled"] is True


def test_current_energy_price_uses_active_period_and_contractual_sun_club(monkeypatch):
    class FixedDateTime:
        @classmethod
        def now(cls, _timezone):
            return measurements.datetime.fromisoformat("2026-04-01T12:30:00+02:00")

    monkeypatch.setattr(sensor, "datetime", FixedDateTime)
    coordinator = SimpleNamespace(
        data=SimpleNamespace(
            tariff={
                "period_prices": {"punta": 0.30, "llano": 0.20, "valle": 0.10},
                "sun_club_enabled": True,
            }
        )
    )

    assert sensor._current_energy_price(coordinator) == 0.165


def test_current_energy_price_does_not_discount_non_sun_club_product(monkeypatch):
    class FixedDateTime:
        @classmethod
        def now(cls, _timezone):
            return measurements.datetime.fromisoformat("2026-04-01T12:30:00+02:00")

    monkeypatch.setattr(sensor, "datetime", FixedDateTime)
    coordinator = SimpleNamespace(
        data=SimpleNamespace(
            tariff={
                "period_prices": {"punta": 0.30, "llano": 0.20, "valle": 0.10},
                "sun_club_enabled": False,
            }
        )
    )

    assert sensor._current_energy_price(coordinator) == 0.30


def test_sun_club_binary_sensor_is_off_for_non_sun_club_product(monkeypatch):
    coordinator = SimpleNamespace(
        data=SimpleNamespace(tariff={"sun_club_enabled": False}),
        selection=SimpleNamespace(account_hash="hash"),
    )
    entity = binary_sensor.OctopusSunClubWindowSensor(coordinator)
    entity.coordinator = coordinator

    assert entity.is_on is False


def test_single_period_tariff_maps_one_price_to_all_periods():
    tariff = mappers.tariff_data(
        {"code": "OCTOPUS-RELAX", "params": "{}"},
        {},
        {"variableTerm": [0.15]},
        [0.15],
        [],
    )

    assert tariff["period_prices"] == {
        "punta": 0.15,
        "llano": 0.15,
        "valle": 0.15,
    }


def test_tariff_mapper_does_not_infer_sun_club_from_future_rollover_product():
    tariff = mappers.tariff_data(
        {
            "code": "OCTOPUS-RELAX",
            "params": '{"solar_product_rollover_code": "SUNCLUB-FUTURE"}',
        },
        {},
        {"variableTerm": [0.15]},
        [0.15],
        [],
    )

    assert tariff["sun_club_enabled"] is False


def test_tariff_mapper_does_not_infer_sun_club_from_unrelated_product():
    tariff = mappers.tariff_data(
        {"code": "OCTOPUS-RELAX", "params": '{"product_type": "FIXED"}'},
        {},
        {"variableTerm": [0.15]},
        [0.15],
        [],
    )

    assert tariff["sun_club_enabled"] is False


def test_hourly_measurement_totals_keep_hourly_points_for_services():
    points = [
        {"start_at": "2026-04-01T10:00:00+02:00", "end_at": "2026-04-01T11:00:00+02:00", "value": 2, "unit": "kwh"},
        {"start_at": "2026-04-01T14:00:00+02:00", "end_at": "2026-04-01T15:00:00+02:00", "value": 3, "unit": "kwh"},
    ]

    result = mappers.measurement_totals(points)

    assert result["points_count"] == 2
    assert result["total_consumption_kwh"] == 5.0
    assert result["last_day_consumption_kwh"] == 5.0


def test_hourly_chart_series_are_bucketed_for_dashboard_bars():
    points = [
        {"start_at": "2026-04-01T00:00:00+02:00", "end_at": "2026-04-01T01:00:00+02:00", "value": 1, "unit": "kwh"},
        {"start_at": "2026-04-01T10:00:00+02:00", "end_at": "2026-04-01T11:00:00+02:00", "value": 2, "unit": "kwh"},
        {"start_at": "2026-04-01T14:00:00+02:00", "end_at": "2026-04-01T15:00:00+02:00", "value": 3, "unit": "kwh"},
        {"start_at": "2026-05-01T14:00:00+02:00", "end_at": "2026-05-01T15:00:00+02:00", "value": 4, "unit": "kwh"},
    ]

    result = measurements.measurement_period_series(points)

    assert result["daily"] == [
        {"date": "2026-04-01", "total_kwh": 6.0, "punta_kwh": 2.0, "llano_kwh": 3.0, "valle_kwh": 1.0},
        {"date": "2026-05-01", "total_kwh": 4.0, "punta_kwh": 0.0, "llano_kwh": 4.0, "valle_kwh": 0.0},
    ]
    assert result["monthly"] == [
        {"period": "2026-04", "total_kwh": 6.0, "punta_kwh": 2.0, "llano_kwh": 3.0, "valle_kwh": 1.0},
        {"period": "2026-05", "total_kwh": 4.0, "punta_kwh": 0.0, "llano_kwh": 4.0, "valle_kwh": 0.0},
    ]


def test_flat_dashboard_values_are_derived_from_measurement_series_attributes():
    series = {
        "daily": [
            {"date": "2026-04-29", "kwh": 10.0, "cost_eur": None},
            {"date": "2026-04-30", "kwh": 20.0, "cost_eur": None},
            {"date": "2026-05-01", "kwh": 9.0, "cost_eur": None},
        ]
    }
    hourly_period_series = {
        "daily": [
            {"date": "2026-04-30", "total_kwh": 20.5, "punta_kwh": 10.8, "llano_kwh": 4.3, "valle_kwh": 5.4},
            {"date": "2026-05-01", "total_kwh": 9.0, "punta_kwh": 3.3, "llano_kwh": 2.8, "valle_kwh": 2.9},
        ],
        "monthly": [
            {"period": "2026-05", "total_kwh": 9.0, "punta_kwh": 3.3, "llano_kwh": 2.8, "valle_kwh": 2.9}
        ],
    }
    costs_by_date = {"2026-04-29": 1.24, "2026-04-30": 1.93, "2026-05-01": 1.03}
    now = measurements.datetime.fromisoformat("2026-05-03T12:00:00+02:00")

    assert measurements.latest_period_consumption(hourly_period_series, "total") == 9.0
    assert measurements.latest_period_consumption(hourly_period_series, "punta") == 3.3
    assert measurements.latest_period_consumption(hourly_period_series, "llano") == 2.8
    assert measurements.latest_period_consumption(hourly_period_series, "valle") == 2.9
    assert measurements.current_month_period_consumption(hourly_period_series, "total", now) == 9.0
    assert measurements.current_month_period_consumption(hourly_period_series, "punta", now) == 3.3
    assert measurements.current_month_estimated_cost(costs_by_date, now) == 1.03
    assert measurements.average_daily_consumption(series, 7) == 13.0
    assert measurements.average_daily_consumption(series, 31) == 13.0
    assert measurements.average_daily_cost(costs_by_date, 7) == 1.4
    assert measurements.average_daily_cost(costs_by_date, 31) == 1.4


def test_latest_invoice_uses_modern_invoice_connection_and_minor_units():
    result = mappers.billing_data(
        {},
        [
            {
                "amount_eur": 123.45,
                "issued_date": "2026-05-02",
                "period_start": "2026-04-01",
                "period_end": "2026-05-01",
                "annulled": False,
            }
        ],
    )

    assert result == {
        "last_invoice_amount": 123.45,
        "last_invoice_issued": "2026-05-02",
        "last_invoice_period_start": "2026-04-01",
        "last_invoice_period_end": "2026-05-01",
    }


def test_legacy_statement_fallback_converts_minor_units():
    result = mappers.billing_data(
        {
            "amount": -13622,
            "issuedDate": "2026-05-02",
            "consumptionStartDate": "2026-04-01",
            "consumptionEndDate": "2026-05-01",
        }
    )

    assert result["last_invoice_amount"] == -136.22


def test_ledger_balance_is_converted_from_minor_units_to_euros():
    selection = mappers.AccountSelection(
        account_number="account",
        account_hash="account-hash",
        property_hash="property-hash",
    )
    result = mappers.build_data(
        selection,
        {"data": {"agreement": {}}},
        {
            "data": {
                "accountBillingInfo": {
                    "ledgers": [
                        {"ledgerType": "SPAIN_ELECTRICITY_LEDGER", "balance": -13622}
                    ]
                }
            }
        },
        [],
        {},
    )

    assert result.balances["credit_balance"] == -136.22


def test_credit_amounts_are_exposed_in_euros_not_minor_units():
    payload = {
        "data": {
            "account": {
                "ledgers": [
                    {
                        "transactions": {
                            "edges": [
                                {
                                    "node": {
                                        "__typename": "Credit",
                                        "reasonCode": "SUN_CLUB",
                                        "amounts": {"gross": 999},
                                        "createdAt": "2026-04-08T00:00:00+02:00",
                                    }
                                },
                                {
                                    "node": {
                                        "__typename": "Credit",
                                        "reasonCode": "SUN_CLUB",
                                        "amounts": {"gross": 1140},
                                        "createdAt": "2026-03-09T00:00:00+02:00",
                                    }
                                },
                            ]
                        }
                    }
                ]
            }
        }
    }

    result = mappers.summarize_credits(payload)

    assert result["reason_code_amounts"] == {"SUN_CLUB": 21.39}
    assert result["recent_credits"][0]["amount"] == 9.99


def test_solar_wallet_fields_are_redacted_and_exposed_in_euros():
    payload = {
        "data": {
            "account": {
                "ledgers": [
                    {
                        "ledgerType": "SPAIN_ELECTRICITY_LEDGER",
                        "balance": -500,
                    },
                    {
                        "ledgerType": "SOLAR_WALLET_LEDGER",
                        "balance": 12345,
                        "creditTransferPermissionsData": {
                            "toTargetLedgers": [
                                {
                                    "ledgerNumber": "L-SECRET",
                                    "accountNumber": "A-SECRET",
                                    "validFrom": "2026-05-01T00:00:00+02:00",
                                    "validTo": None,
                                }
                            ]
                        },
                    },
                ]
            }
        }
    }

    result = mappers.summarize_solar_wallet(payload)

    assert result["has_solar_wallet"] is True
    assert result["available_credit_eur"] == 123.45
    assert result["credit_left_eur"] == 123.45
    assert result["relationships_count"] == 1
    assert result["relationships"][0]["target_ledger_hash"] != "L-SECRET"
    assert result["relationships"][0]["target_account_hash"] != "A-SECRET"
    assert "targetGivenName" not in result["relationships"][0]


def test_solar_wallet_is_absent_without_a_solar_wallet_ledger():
    payload = {
        "data": {
            "account": {
                "ledgers": [
                    {"ledgerType": "SPAIN_ELECTRICITY_LEDGER", "balance": -500}
                ]
            }
        }
    }

    result = mappers.summarize_solar_wallet(payload)

    assert result["has_solar_wallet"] is False
    assert result["available_credit_eur"] is None
    assert result["relationships"] == []


def test_intelligent_go_fields_do_not_expose_device_id():
    payload = {
        "data": {
            "eligibleDeviceTypes": ["ELECTRIC_VEHICLES"],
            "devices": [
                {
                    "__typename": "SmartFlexDevice",
                    "id": "device-secret",
                    "name": "private-device-name",
                    "deviceType": "ELECTRIC_VEHICLES",
                    "provider": "TESLA",
                    "propertyId": "property-secret",
                    "status": {
                        "current": "LIVE",
                        "isSuspended": False,
                        "currentState": "ACTIVE",
                    },
                }
            ],
        }
    }
    dispatches = {
        "data": {
            "flexPlannedDispatches": [
                {
                    "start": "2026-05-01T01:00:00+02:00",
                    "end": "2026-05-01T02:00:00+02:00",
                    "type": "CHARGE",
                    "energyAddedKwh": "7.2",
                }
            ]
        }
    }

    result = mappers.summarize_intelligent_go(payload, dispatches)

    assert result["eligible_device_types"] == ["ELECTRIC_VEHICLES"]
    assert "id" not in result["registered_device"]
    assert "name" not in result["registered_device"]
    assert result["registered_device"]["present"] is True
    assert result["registered_device"]["device_type"] == "ELECTRIC_VEHICLES"
    assert result["registered_device"]["status"] == "LIVE"
    assert result["registered_device"]["property_hash"] != "property-secret"
    assert result["registered_devices_count"] == 1
    assert result["planned_dispatches"][0]["energy_added_kwh"] == 7.2


def test_intelligent_go_distinguishes_eligible_from_registered():
    result = mappers.summarize_intelligent_go(
        {"data": {"eligibleDeviceTypes": ["ELECTRIC_VEHICLES"], "devices": []}}
    )

    assert result["eligible_device_types"] == ["ELECTRIC_VEHICLES"]
    assert result["registered_device"]["present"] is False
    assert result["registered_devices_count"] == 0
