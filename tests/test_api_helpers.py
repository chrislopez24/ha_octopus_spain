import asyncio
from datetime import date, datetime, timedelta, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import types


ROOT = Path(__file__).parents[1]
PACKAGE = types.ModuleType("custom_components.octopus_spain")
PACKAGE.__path__ = [str(ROOT / "custom_components" / "octopus_spain")]
sys.modules.setdefault("custom_components.octopus_spain", PACKAGE)


def load_module(name: str):
    spec = spec_from_file_location(
        f"custom_components.octopus_spain.{name}",
        ROOT / "custom_components" / "octopus_spain" / f"{name}.py",
    )
    assert spec and spec.loader
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_REDACTION = load_module("redaction")
redact_sensitive_value = _REDACTION.redact_sensitive_value
stable_hash = _REDACTION.stable_hash


def test_redact_sensitive_value_hides_signed_urls_and_authorization_tokens():
    assert redact_sensitive_value("https://example.invalid/file.pdf?X-Amz-Signature=secret") == "<redacted-url>"
    assert redact_sensitive_value("Bearer abc.def.ghi") == "<redacted-token>"


def test_stable_hash_is_deterministic_and_short():
    assert stable_hash("sensitive-id") == stable_hash("sensitive-id")
    assert len(stable_hash("sensitive-id")) == 12


def test_service_date_range_defaults_to_closed_recent_window(monkeypatch):
    class FakeDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 5, 3)

    service_helpers = load_module("service_helpers")
    monkeypatch.setattr(service_helpers, "date", FakeDate)

    result = service_helpers.service_date_range({})

    assert result.end == date(2026, 5, 1)
    assert result.start == date(2026, 5, 1) - timedelta(days=31)


def test_madrid_midnight_range_aligns_measurement_queries_to_complete_days():
    service_helpers = load_module("service_helpers")
    result = service_helpers.service_date_range(
        {"start_date": date(2026, 4, 1), "end_date": date(2026, 4, 30)}
    )

    start_at, end_at = service_helpers.madrid_midnight_range(result)

    assert start_at.isoformat() == "2026-04-01T00:00:00+02:00"
    assert end_at.isoformat() == "2026-04-30T00:00:00+02:00"


def test_measurement_variables_preserve_madrid_midnight_when_serialized():
    api = load_module("api")
    service_helpers = load_module("service_helpers")
    date_range = service_helpers.service_date_range(
        {"start_date": date(2026, 5, 1), "end_date": date(2026, 5, 2)}
    )
    start_at, end_at = service_helpers.madrid_midnight_range(date_range)

    result = api.OctopusSpainClient._measurement_variables("property-id", start_at, end_at, "HOUR_INTERVAL", 24)

    assert datetime.fromisoformat(result["startAt"].replace("Z", "+00:00")).astimezone(
        service_helpers.MADRID
    ).isoformat() == "2026-05-01T00:00:00+02:00"


def test_invoice_payload_exposes_human_labels_and_stable_indexes():
    api = load_module("api")
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


def test_invoice_document_fetches_fresh_signed_url_even_if_old_url_was_seen():
    api = load_module("api")
    client = api.OctopusSpainClient(session=None, email="user@example.invalid", password="secret")
    client._invoice_id_cache["abc123"] = 123
    client._invoice_url_cache = {"abc123": "https://example.invalid/expired.txt"}
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


def test_utc_midnight_would_shift_hourly_measurements_during_dst():
    service_helpers = load_module("service_helpers")
    start_at = datetime.combine(date(2026, 5, 1), datetime.min.time(), timezone.utc)

    assert start_at.astimezone(service_helpers.MADRID).isoformat() == "2026-05-01T02:00:00+02:00"


def test_service_date_range_respects_explicit_dates():
    service_helpers = load_module("service_helpers")

    result = service_helpers.service_date_range(
        {"start_date": date(2026, 4, 1), "end_date": date(2026, 4, 30)}
    )

    assert result.start == date(2026, 4, 1)
    assert result.end == date(2026, 4, 30)
