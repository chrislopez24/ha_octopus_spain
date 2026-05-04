import asyncio
import base64
from datetime import date, datetime, timedelta, timezone
import json

from custom_components.octopus_spain import api, redaction, service_helpers


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


def test_expired_jwt_graphql_error_is_classified_as_auth_error():
    client = api.OctopusSpainClient(session=None, email="user@example.invalid", password="secret")
    payload = {"errors": [{"message": "Signature of the JWT has expired."}]}

    try:
        client._handle_graphql_response("ViewerAccount", payload)
    except api.OctopusSpainAuthError:
        pass
    else:
        raise AssertionError("JWT expiration should trigger auth retry handling")


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


def test_utc_midnight_would_shift_hourly_measurements_during_dst():
    start_at = datetime.combine(date(2026, 5, 1), datetime.min.time(), timezone.utc)

    assert start_at.astimezone(service_helpers.MADRID).isoformat() == "2026-05-01T02:00:00+02:00"


def test_service_date_range_respects_explicit_dates():
    result = service_helpers.service_date_range(
        {"start_date": date(2026, 4, 1), "end_date": date(2026, 4, 30)}
    )

    assert result.start == date(2026, 4, 1)
    assert result.end == date(2026, 4, 30)
