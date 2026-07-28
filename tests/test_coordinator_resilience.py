import asyncio
from types import SimpleNamespace

from custom_components.octopus_spain import api, coordinator


def make_coordinator(previous=None):
    instance = object.__new__(coordinator.OctopusSpainCoordinator)
    instance.data = previous
    return instance


def test_optional_failure_returns_empty_without_previous_data():
    instance = make_coordinator()

    async def failing_request():
        raise api.OctopusSpainError("temporary")

    result = asyncio.run(instance._optional_data("credits", failing_request(), {}))

    assert result == {}


def test_optional_failure_retains_last_valid_data_as_stale():
    previous = SimpleNamespace(credits={"count": 3, "reason_code_counts": {"A": 3}})
    instance = make_coordinator(previous)

    async def failing_request():
        raise api.OctopusSpainTemporaryError("temporary")

    result = asyncio.run(instance._optional_data("credits", failing_request(), {}))

    assert result["count"] == 3
    assert result["stale"] is True
    assert result["error"] == "unavailable"
    assert "stale" not in previous.credits


def test_optional_auth_failure_still_reauthenticates_entry():
    instance = make_coordinator()

    async def failing_request():
        raise api.OctopusSpainAuthError("expired")

    try:
        asyncio.run(instance._optional_data("credits", failing_request(), {}))
    except api.OctopusSpainAuthError:
        pass
    else:
        raise AssertionError("Authentication failures must not be degraded")
