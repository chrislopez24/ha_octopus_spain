from datetime import date, timedelta
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


def test_service_date_range_respects_explicit_dates():
    service_helpers = load_module("service_helpers")

    result = service_helpers.service_date_range(
        {"start_date": date(2026, 4, 1), "end_date": date(2026, 4, 30)}
    )

    assert result.start == date(2026, 4, 1)
    assert result.end == date(2026, 4, 30)
