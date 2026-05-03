#!/usr/bin/env python3
"""Catalog GraphQL operations observed in local HAR files safely.

The generated markdown documents operation names, variable keys and selected
field names. It must not include response values, variables values, cookies,
tokens, CUPS, account numbers, addresses, emails or signed URLs.
"""

from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "octopus-spain-har-operation-catalog.md"

SENSITIVE_FIELD_NAMES = {
    "email",
    "mobile",
    "nif",
    "billingAddress",
    "billingAddressPostcode",
    "billingAddressLine1",
    "billingAddressLine2",
    "billingAddressLine3",
    "billingAddressLine4",
    "address",
    "splitAddress",
    "richAddress",
    "streetAddress",
    "cups",
    "pdfUrl",
    "referralUrl",
    "referredUserName",
}


def extract_operation_blocks(query: str) -> list[str]:
    """Extract field-like tokens from a GraphQL document."""

    cleaned = re.sub(r'""".*?"""', "", query, flags=re.S)
    cleaned = re.sub(r"#.*", "", cleaned)
    tokens = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", cleaned)
    ignored = {
        "query",
        "mutation",
        "fragment",
        "on",
        "true",
        "false",
        "null",
        "String",
        "Int",
        "ID",
        "Date",
        "DateTime",
        "Boolean",
        "first",
        "after",
        "before",
        "orderBy",
        "status",
    }
    fields: list[str] = []
    for token in tokens:
        if token in ignored or token.startswith("get") and token.endswith("_Account"):
            continue
        if token not in fields:
            fields.append(token)
    return fields


def safe_field(field: str) -> str:
    if field in SENSITIVE_FIELD_NAMES:
        return f"{field} (sensible/no exponer)"
    return field


def main() -> int:
    operations: dict[str, dict[str, object]] = {}
    for path in sorted(ROOT.glob("*.har")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for entry in data.get("log", {}).get("entries", []):
            request = entry.get("request", {})
            url = request.get("url", "")
            if "graphql" not in url.lower() and "kraken" not in url.lower():
                continue
            text = request.get("postData", {}).get("text", "") or ""
            try:
                payload = json.loads(text)
                if isinstance(payload, list):
                    payload = payload[0]
            except Exception:
                continue
            operation = payload.get("operationName") or "<anonymous>"
            query = payload.get("query") or ""
            variables = payload.get("variables") or {}
            item = operations.setdefault(
                operation,
                {
                    "files": set(),
                    "endpoints": set(),
                    "variable_keys": set(),
                    "fields": [],
                },
            )
            item["files"].add(path.name)
            item["endpoints"].add(url.split("?")[0])
            item["variable_keys"].update(variables.keys())
            for field in extract_operation_blocks(query):
                if field not in item["fields"]:
                    item["fields"].append(field)
    lines = [
        "# Octopus Spain HAR GraphQL operation catalog",
        "",
        "Catálogo generado desde HARs locales ignorados por Git. No incluye valores de variables ni respuestas.",
        "",
    ]
    for operation in sorted(operations):
        item = operations[operation]
        lines.extend(
            [
                f"## `{operation}`",
                "",
                f"- HARs: {', '.join(sorted(item['files']))}",
                f"- Endpoints: {', '.join(sorted(item['endpoints']))}",
                f"- Variables: {', '.join(sorted(item['variable_keys'])) or 'ninguna'}",
                "- Campos observados:",
            ]
        )
        for field in item["fields"]:
            lines.append(f"  - `{safe_field(field)}`")
        lines.append("")
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
