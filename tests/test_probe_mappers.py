from tools.probe_octopus_endpoints import summarize_credits, summarize_measurements


def test_summarize_credits_counts_arbitrary_reason_codes_without_user_values():
    payload = {
        "data": {
            "account": {
                "ledgers": [
                    {
                        "transactions": {
                            "edges": [
                                {"node": {"__typename": "Credit", "reasonCode": "REASON_A", "id": "internal-id-1", "amounts": {"gross": 1}}},
                                {"node": {"__typename": "Credit", "reasonCode": "REASON_B", "id": "internal-id-2", "amounts": {"gross": 2}}},
                                {"node": {"__typename": "Credit", "reasonCode": "REASON_A", "id": "internal-id-3", "amounts": {"gross": 3}}},
                                {"node": {"__typename": "Debit", "reasonCode": "IGNORED"}},
                            ]
                        }
                    }
                ]
            }
        }
    }

    result = summarize_credits(payload)

    assert result["credit_edges_count"] == 3
    assert result["reason_code_counts"] == {"REASON_A": 2, "REASON_B": 1}


def test_summarize_measurements_reports_shape_and_cost_presence_for_any_user():
    payload = {
        "data": {
            "property": {
                "measurements": {
                    "edges": [
                        {
                            "node": {
                                "value": "1.5",
                                "unit": "kwh",
                                "startAt": "2026-01-01T00:00:00+01:00",
                                "endAt": "2026-01-02T00:00:00+01:00",
                                "metaData": {
                                    "statistics": [
                                        {"costInclTax": {"estimatedAmount": "0.30"}, "costExclTax": {"estimatedAmount": "0.20"}}
                                    ]
                                },
                            }
                        },
                        {
                            "node": {
                                "value": "2.0",
                                "unit": "kwh",
                                "startAt": "2026-01-02T00:00:00+01:00",
                                "endAt": "2026-01-03T00:00:00+01:00",
                                "metaData": {"statistics": []},
                            }
                        },
                    ]
                }
            }
        }
    }

    result = summarize_measurements(payload)

    assert result["edges_count"] == 2
    assert result["units"] == ["kwh"]
    assert result["cost_incl_tax_present"] is True
    assert result["cost_excl_tax_present"] is True
