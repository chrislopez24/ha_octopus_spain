import asyncio
import base64
from datetime import date, datetime, timedelta, timezone
import json
from types import SimpleNamespace

from custom_components.octopus_spain import api, mappers, redaction, service_helpers


def fake_jwt(exp: int) -> str:
    def encode(payload):
        raw = json.dumps(payload, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    return f"{encode({'alg': 'none', 'typ': 'JWT'})}.{encode({'exp': exp})}.signature"


def test_redact_sensitive_value_hides_signed_urls_and_authorization_tokens():
    assert redaction.redact_sensitive_value("https://example.invalid/file.pdf?X-Amz-Signature=secret") == "<redacted-url>"
    assert redaction.redact_sensitive_value("Bearer abc.def.ghi") == "<redacted-token>"


def test_stable_hash_is_deterministic_and_short():
    assert redaction.stable_hash("sensitive-id") == redaction.stable_hash("sensitive-id")
    assert len(redaction.stable_hash("sensitive-id")) == 12


def test_service_date_range_defaults_to_closed_recent_window(monkeypatch):
    class FakeDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 5, 3)

    monkeypatch.setattr(service_helpers, "date", FakeDate)

    result = service_helpers.service_date_range({})

    assert result.end == date(2026, 5, 1)
    assert result.start == date(2026, 5, 1) - timedelta(days=31)


def test_madrid_midnight_range_aligns_measurement_queries_to_complete_days():
    result = service_helpers.service_date_range(
        {"start_date": date(2026, 4, 1), "end_date": date(2026, 4, 30)}
    )

    start_at, end_at = service_helpers.madrid_midnight_range(result)

    assert start_at.isoformat() == "2026-04-01T00:00:00+02:00"
    assert end_at.isoformat() == "2026-04-30T00:00:00+02:00"


def test_measurement_variables_preserve_madrid_midnight_when_serialized():
    date_range = service_helpers.service_date_range(
        {"start_date": date(2026, 5, 1), "end_date": date(2026, 5, 2)}
    )
    start_at, end_at = service_helpers.madrid_midnight_range(date_range)

    result = api.OctopusSpainClient._measurement_variables("property-id", start_at, end_at, "HOUR_INTERVAL", 24)

    assert datetime.fromisoformat(result["startAt"].replace("Z", "+00:00")).astimezone(
        service_helpers.MADRID
    ).isoformat() == "2026-05-01T00:00:00+02:00"


def measurement_edge(index: int) -> dict:
    return {
        "node": {
            "value": "1",
            "unit": "kwh",
            "startAt": f"2025-10-01T{index % 24:02d}:00:00+02:00",
            "endAt": f"2025-10-01T{(index + 1) % 24:02d}:00:00+02:00",
            "metaData": {"statistics": []},
        }
    }


def test_credits_follow_has_next_page_and_aggregate_all_pages(monkeypatch):
    client = api.OctopusSpainClient(session=None, email="user@example.invalid", password="secret")
    calls = []

    def credit_edge(amount: int, reason: str) -> dict:
        return {
            "node": {
                "__typename": "Credit",
                "amounts": {"gross": amount},
                "createdAt": "2026-01-01T00:00:00Z",
                "reasonCode": reason,
            }
        }

    async def fake_graphql(_operation_name, _query, variables):
        calls.append(variables.copy())
        if variables["after"] is None:
            return {
                "data": {
                    "account": {
                        "ledgers": [
                            {
                                "transactions": {
                                    "pageInfo": {"hasNextPage": True, "endCursor": "credit-cursor"},
                                    "edges": [credit_edge(100, "A")],
                                }
                            }
                        ]
                    }
                }
            }
        return {
            "data": {
                "account": {
                    "ledgers": [
                        {
                            "transactions": {
                                "pageInfo": {"hasNextPage": False, "endCursor": None},
                                "edges": [credit_edge(200, "B")],
                            }
                        }
                    ]
                }
            }
        }

    client.async_graphql = fake_graphql
    result = asyncio.run(client.async_credits("account", "ledger"))

    assert [call["after"] for call in calls] == [None, "credit-cursor"]
    assert all(call["fromDate"] == f"{date.today().year - 5}-01-01" for call in calls)
    assert result["count"] == 2
    assert result["reason_code_amounts"] == {"A": 1.0, "B": 2.0}
    assert result["truncated"] is False


def test_measurements_follow_has_next_page_and_return_all_edges():
    client = api.OctopusSpainClient(session=None, email="user@example.invalid", password="secret")
    calls = []

    async def fake_graphql(operation_name, _query, variables):
        calls.append((operation_name, variables["after"]))
        if variables["after"] is None:
            return {
                "data": {
                    "property": {
                        "measurements": {
                            "totalCount": 3,
                            "pageInfo": {"hasNextPage": True, "endCursor": "cursor-1"},
                            "edges": [measurement_edge(0), measurement_edge(1)],
                        }
                    }
                }
            }
        return {
            "data": {
                "property": {
                    "measurements": {
                        "totalCount": 3,
                        "pageInfo": {"hasNextPage": False, "endCursor": "cursor-2"},
                        "edges": [measurement_edge(2)],
                    }
                }
            }
        }

    client.async_graphql = fake_graphql
    result = asyncio.run(
        client.async_measurements(
            "property",
            datetime.fromisoformat("2025-10-01T00:00:00+02:00"),
            datetime.fromisoformat("2025-10-02T00:00:00+02:00"),
            "HOUR_INTERVAL",
            2,
        )
    )

    assert calls == [("getAccountMeasurements", None), ("getAccountMeasurements", "cursor-1")]
    assert result["points_count"] == 3
    assert result["total_count"] == 3
    assert result["truncated"] is False


def test_october_2025_dst_range_returns_all_745_hourly_points():
    client = api.OctopusSpainClient(session=None, email="user@example.invalid", password="secret")
    pages = [
        {
            "data": {
                "property": {
                    "measurements": {
                        "totalCount": 745,
                        "pageInfo": {"hasNextPage": True, "endCursor": "cursor-744"},
                        "edges": [measurement_edge(index) for index in range(744)],
                    }
                }
            }
        },
        {
            "data": {
                "property": {
                    "measurements": {
                        "totalCount": 745,
                        "pageInfo": {"hasNextPage": False, "endCursor": "cursor-745"},
                        "edges": [measurement_edge(744)],
                    }
                }
            }
        },
    ]

    async def fake_graphql(_operation_name, _query, variables):
        assert variables["after"] == (None if len(pages) == 2 else "cursor-744")
        return pages.pop(0)

    client.async_graphql = fake_graphql
    result = asyncio.run(
        client.async_measurements(
            "property",
            datetime.fromisoformat("2025-10-01T00:00:00+02:00"),
            datetime.fromisoformat("2025-11-01T00:00:00+01:00"),
            "HOUR_INTERVAL",
            744,
        )
    )

    assert result["points_count"] == 745
    assert len(result["points"]) == 745
    assert result["total_count"] == 745
    assert result["truncated"] is False


def test_measurement_pagination_rejects_missing_next_cursor():
    client = api.OctopusSpainClient(session=None, email="user@example.invalid", password="secret")

    async def fake_graphql(_operation_name, _query, _variables):
        return {
            "data": {
                "property": {
                    "measurements": {
                        "pageInfo": {"hasNextPage": True, "endCursor": None},
                        "edges": [measurement_edge(0)],
                    }
                }
            }
        }

    client.async_graphql = fake_graphql
    try:
        asyncio.run(
            client.async_measurements(
                "property",
                datetime.fromisoformat("2025-10-01T00:00:00+02:00"),
                datetime.fromisoformat("2025-10-02T00:00:00+02:00"),
                "HOUR_INTERVAL",
                744,
            )
        )
    except api.OctopusSpainGraphQLError:
        pass
    else:
        raise AssertionError("A missing next cursor must not silently truncate measurements")


def test_account_selection_rejects_ambiguous_multiple_accounts():
    account_payload = {
        "data": {
            "viewer": {
                "accounts": [
                    {"number": "A-1", "ledgers": [{"ledgerType": "SPAIN_ELECTRICITY_LEDGER", "number": "L-1"}]},
                    {"number": "A-2", "ledgers": [{"ledgerType": "SPAIN_ELECTRICITY_LEDGER", "number": "L-2"}]},
                ]
            }
        }
    }
    property_payload = {
        "data": {
            "viewer": {
                "accounts": [
                    {"number": "A-1", "properties": [{"id": "P-1", "electricitySupplyPoints": [{"activeAgreement": {"id": "AG-1"}}]}]},
                    {"number": "A-2", "properties": [{"id": "P-2", "electricitySupplyPoints": [{"activeAgreement": {"id": "AG-2"}}]}]},
                ]
            }
        }
    }

    assert len(mappers.account_selections(account_payload, property_payload)) == 2
    try:
        mappers.select_default_account(account_payload, property_payload)
    except ValueError as err:
        assert "Multiple" in str(err)
    else:
        raise AssertionError("Ambiguous accounts must not select the first item")


def test_account_selections_include_each_usable_property():
    account_payload = {
        "data": {
            "viewer": {
                "accounts": [
                    {"number": "A", "ledgers": [{"ledgerType": "SPAIN_ELECTRICITY_LEDGER", "number": "L"}]}
                ]
            }
        }
    }
    property_payload = {
        "data": {
            "viewer": {
                "accounts": [
                    {
                        "number": "A",
                        "properties": [
                            {"id": "P1", "electricitySupplyPoints": [{"activeAgreement": {"id": "AG1"}}]},
                            {"id": "P2", "electricitySupplyPoints": [{"activeAgreement": {"id": "AG2"}}]},
                        ],
                    }
                ]
            }
        }
    }

    selections = mappers.account_selections(account_payload, property_payload)

    assert [selection.property_id for selection in selections] == ["P1", "P2"]


def test_services_require_config_entry_id_when_multiple_entries_are_loaded():
    entries = [
        SimpleNamespace(entry_id="one", runtime_data=SimpleNamespace(name="one")),
        SimpleNamespace(entry_id="two", runtime_data=SimpleNamespace(name="two")),
    ]
    hass = SimpleNamespace(config_entries=SimpleNamespace(async_entries=lambda _domain: entries))

    try:
        service_helpers.select_runtime_data(entries, {})
    except Exception as err:
        assert "config_entry_id is required" in str(err)
    else:
        raise AssertionError("Ambiguous service target must be rejected")
    assert service_helpers.select_runtime_data(entries, {"config_entry_id": "two"}).name == "two"


def test_invoice_payload_exposes_human_labels_and_stable_indexes():
    client = api.OctopusSpainClient(session=None, email="user@example.invalid", password="secret")
    payload = {
        "data": {
            "account": {
                "ledgers": [
                    {
                        "invoices": {
                            "edges": [
                                {
                                    "node": {
                                        "id": 123,
                                        "consumptionStartDate": "2026-04-01T00:00:00+02:00",
                                        "consumptionEndDate": "2026-05-01T00:00:00+02:00",
                                        "invoicedAmount": 12345,
                                        "issuedDate": "2026-05-02",
                                        "annulledBy": None,
                                        "isHeld": False,
                                    }
                                },
                                {
                                    "node": {
                                        "id": 122,
                                        "consumptionStartDate": "2026-03-01T00:00:00+01:00",
                                        "consumptionEndDate": "2026-04-01T00:00:00+02:00",
                                    }
                                },
                            ]
                        }
                    }
                ]
            }
        }
    }

    result = client._redact_invoice_payload(payload, "account", "ledger")

    assert result[0]["index"] == 0
    assert result[0]["period_label"] == "2026-04-01 a 2026-05-01"
    assert result[0]["label"] == "Factura 2026-04-01 a 2026-05-01"
    assert result[0]["amount_eur"] == 123.45
    assert result[0]["issued_date"] == "2026-05-02"
    assert result[1]["index"] == 1
    assert client._invoice_hashes == [result[0]["invoice_id_hash"], result[1]["invoice_id_hash"]]


def test_invoice_document_fetches_fresh_signed_url_on_demand():
    client = api.OctopusSpainClient(session=None, email="user@example.invalid", password="secret")
    client._invoice_id_cache["abc123"] = 123
    client._account_number = "account"
    client._ledger_number = "ledger"

    async def fake_fetch_bill_url(account_number, ledger_number, invoice_id):
        assert account_number == "account"
        assert ledger_number == "ledger"
        assert invoice_id == 123
        return "https://example.invalid/fresh.pdf"

    client._async_fetch_bill_url = fake_fetch_bill_url

    document = asyncio.run(client.async_get_invoice_document("abc123"))

    assert document.url == "https://example.invalid/fresh.pdf"


class FakeResponse:
    def __init__(self, *, status=200, json_result=None, json_error=None):
        self.status = status
        self._json_result = json_result
        self._json_error = json_error

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def raise_for_status(self):
        return None

    async def json(self, **_kwargs):
        if self._json_error:
            raise self._json_error
        return self._json_result


def test_post_preserves_http_error_classification():
    cases = [
        (401, api.OctopusSpainAuthError),
        (403, api.OctopusSpainPermissionError),
        (429, api.OctopusSpainRateLimitError),
        (503, api.OctopusSpainTemporaryError),
    ]
    for status, expected in cases:
        async def post(*_args, **_kwargs):
            return FakeResponse(status=status)

        session = SimpleNamespace(post=post)
        client = api.OctopusSpainClient(session, "user@example.invalid", "secret")
        if status == 401:
            client._token = "token"
        try:
            asyncio.run(client._post({"operationName": "Test"}, include_auth=status == 401))
        except expected:
            pass
        else:
            raise AssertionError(f"HTTP {status} must map to {expected.__name__}")


def test_post_normalizes_transport_timeout():
    class TimeoutSession:
        async def post(self, *_args, **_kwargs):
            await asyncio.sleep(3600)

    client = api.OctopusSpainClient(TimeoutSession(), "user@example.invalid", "secret")
    original_wait_for = api.asyncio.wait_for

    async def immediate_timeout(awaitable, timeout):
        awaitable.close()
        raise asyncio.TimeoutError

    api.asyncio.wait_for = immediate_timeout
    try:
        try:
            asyncio.run(client._post({"operationName": "Test"}, include_auth=False))
        except api.OctopusSpainError as err:
            assert str(err) == "Cannot connect to Octopus"
        else:
            raise AssertionError("Timeout must be normalized")
    finally:
        api.asyncio.wait_for = original_wait_for


def test_post_normalizes_invalid_json_response():
    class InvalidJsonSession:
        async def post(self, *_args, **_kwargs):
            return FakeResponse(json_error=json.JSONDecodeError("bad", "", 0))

    client = api.OctopusSpainClient(InvalidJsonSession(), "user@example.invalid", "secret")
    try:
        asyncio.run(client._post({"operationName": "Test"}, include_auth=False))
    except api.OctopusSpainError as err:
        assert str(err) == "Octopus returned an invalid response"
    else:
        raise AssertionError("Invalid JSON must be normalized")


def test_expired_jwt_graphql_error_is_classified_as_auth_error():
    client = api.OctopusSpainClient(session=None, email="user@example.invalid", password="secret")
    payload = {"errors": [{"message": "Signature of the JWT has expired."}]}

    try:
        client._handle_graphql_response("ViewerAccount", payload)
    except api.OctopusSpainAuthError:
        pass
    else:
        raise AssertionError("JWT expiration should trigger auth retry handling")


def test_graphql_permission_error_is_not_classified_as_auth():
    client = api.OctopusSpainClient(session=None, email="user@example.invalid", password="secret")
    payload = {
        "errors": [
            {"message": "Permission denied", "extensions": {"code": "PERMISSION_DENIED"}}
        ]
    }

    try:
        client._handle_graphql_response("OptionalFeature", payload)
    except api.OctopusSpainPermissionError:
        pass
    except api.OctopusSpainAuthError as err:
        raise AssertionError("Permission errors must not trigger reauthentication") from err
    else:
        raise AssertionError("Permission error must be classified")


def test_graphql_rate_limit_and_temporary_errors_have_distinct_types():
    client = api.OctopusSpainClient(session=None, email="user@example.invalid", password="secret")
    cases = [
        ("RATE_LIMITED", api.OctopusSpainRateLimitError),
        ("SERVICE_UNAVAILABLE", api.OctopusSpainTemporaryError),
    ]
    for code, expected in cases:
        try:
            client._handle_graphql_response(
                "Test", {"errors": [{"message": "safe", "extensions": {"code": code}}]}
            )
        except expected:
            pass
        else:
            raise AssertionError(f"{code} must map to {expected.__name__}")


def test_expired_jwt_graphql_error_reauthenticates_and_retries_once():
    client = api.OctopusSpainClient(session=None, email="user@example.invalid", password="secret")
    calls = []

    async def fake_post(payload, include_auth):
        calls.append((payload["operationName"], include_auth))
        if not include_auth:
            return {"data": {"obtainKrakenToken": {"token": "fresh-token"}}}
        if calls.count(("ViewerAccount", True)) == 1:
            return client._handle_graphql_response(
                "ViewerAccount",
                {"errors": [{"message": "Signature of the JWT has expired."}]},
            )
        return {"data": {"viewer": {"id": "ok"}}}

    client._post = fake_post

    result = asyncio.run(client.async_graphql("ViewerAccount", "query", {}))

    assert result == {"data": {"viewer": {"id": "ok"}}}
    assert calls == [
        ("obtainKrakenToken", False),
        ("ViewerAccount", True),
        ("obtainKrakenToken", False),
        ("ViewerAccount", True),
    ]


def test_graphql_uses_refresh_token_when_current_jwt_is_missing(monkeypatch):
    monkeypatch.setattr(api.time, "time", lambda: 1_000)
    client = api.OctopusSpainClient(session=None, email="user@example.invalid", password="secret")
    client._refresh_token = "refresh-old"
    client._refresh_expires_at = 1_000_000
    calls = []

    async def fake_post(payload, include_auth):
        calls.append((payload["operationName"], include_auth, payload["variables"]["input"] if not include_auth else None))
        if not include_auth:
            return {
                "data": {
                    "obtainKrakenToken": {
                        "token": fake_jwt(2_000),
                        "refreshToken": "refresh-new",
                        "refreshExpiresIn": 1_000_000,
                    }
                }
            }
        return {"data": {"viewer": {"id": "ok"}}}

    client._post = fake_post

    result = asyncio.run(client.async_graphql("ViewerAccount", "query", {}))

    assert result == {"data": {"viewer": {"id": "ok"}}}
    assert calls[0] == ("obtainKrakenToken", False, {"refreshToken": "refresh-old"})
    assert calls[1] == ("ViewerAccount", True, None)
    assert client._refresh_token == "refresh-new"


def test_graphql_refreshes_jwt_before_expiration(monkeypatch):
    monkeypatch.setattr(api.time, "time", lambda: 1_000)
    client = api.OctopusSpainClient(session=None, email="user@example.invalid", password="secret")
    client._token = fake_jwt(1_100)
    client._token_expires_at = 1_100
    client._refresh_token = "refresh-token"
    client._refresh_expires_at = 1_000_000
    calls = []

    async def fake_post(payload, include_auth):
        calls.append((payload["operationName"], include_auth))
        if not include_auth:
            return {
                "data": {
                    "obtainKrakenToken": {
                        "token": fake_jwt(2_000),
                        "refreshToken": "refresh-token",
                        "refreshExpiresIn": 1_000_000,
                    }
                }
            }
        return {"data": {"viewer": {"id": "ok"}}}

    client._post = fake_post

    result = asyncio.run(client.async_graphql("ViewerAccount", "query", {}))

    assert result == {"data": {"viewer": {"id": "ok"}}}
    assert calls == [("obtainKrakenToken", False), ("ViewerAccount", True)]
    assert client._token_expires_at == 2_000


def test_half_open_measurement_range_spans_october_dst_without_including_november():
    date_range = service_helpers.DateRange(date(2025, 10, 1), date(2025, 11, 1))
    start_at, end_at = service_helpers.madrid_midnight_range(date_range)

    assert start_at.isoformat() == "2025-10-01T00:00:00+02:00"
    assert end_at.isoformat() == "2025-11-01T00:00:00+01:00"
    assert (end_at.timestamp() - start_at.timestamp()) / 3600 == 745


def test_utc_midnight_would_shift_hourly_measurements_during_dst():
    start_at = datetime.combine(date(2026, 5, 1), datetime.min.time(), timezone.utc)

    assert start_at.astimezone(service_helpers.MADRID).isoformat() == "2026-05-01T02:00:00+02:00"


def test_service_date_range_respects_explicit_dates():
    result = service_helpers.service_date_range(
        {"start_date": date(2026, 4, 1), "end_date": date(2026, 4, 30)}
    )

    assert result.start == date(2026, 4, 1)
    assert result.end == date(2026, 4, 30)
