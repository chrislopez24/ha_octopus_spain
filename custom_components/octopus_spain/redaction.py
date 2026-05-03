"""Redaction helpers for Octopus Energy Spain.

This module intentionally has no Home Assistant imports so it can be unit tested
without a Home Assistant test environment.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any


def stable_hash(value: str | None) -> str:
    """Return a short stable hash for sensitive identifiers."""

    if not value:
        return "unknown"
    return sha256(value.encode("utf-8")).hexdigest()[:12]


def redact_sensitive_value(value: Any) -> Any:
    """Redact operational secrets before they can reach logs or diagnostics."""

    if not isinstance(value, str):
        return value
    lowered = value.lower()
    if "x-amz-signature" in lowered or "x-amz-credential" in lowered:
        return "<redacted-url>"
    if value.startswith(("Bearer ", "JWT ")) or value.count(".") >= 2:
        return "<redacted-token>"
    if "authorization" in lowered or "token" in lowered:
        return "<redacted-token>"
    return value
