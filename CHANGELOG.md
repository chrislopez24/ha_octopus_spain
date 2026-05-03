# Changelog

## 0.0.4 - 2026-05-03

Invoice UX release.

### Added

- Human-readable invoice labels and indexes in `recent_invoices`.
- `octopus_spain.get_latest_invoice_document` response service.
- `octopus_spain.get_invoice_document_by_index` response service for dashboard cards.

### Changed

- Invoice document URLs remain generated only on demand and are not persisted in entity attributes.

## 0.0.3 - 2026-05-03

Dashboard usability release.

### Added

- Flat dashboard sensors for latest complete day and current month consumption split by total, Punta, Llano and Valle.
- Flat sensors for current month estimated cost and 7/31 day daily averages.
- `measurement` state class metadata for price, consumption and cost sensors where appropriate.
- Estimated-cost attributes that state whether power term and taxes are included.

### Changed

- Refresh Octopus data hourly and notify entities on each coordinator refresh so time-derived values update more reliably.
- Shortened the README and moved technical detail references to `docs/`.

## 0.0.2 - 2026-05-03

Maintenance release.

### Fixed

- Preserve Europe/Madrid day boundaries when serializing measurement service ranges.
- Return native `date` values for Home Assistant date sensors.

### Changed

- Bumped the integration version for the next HACS release.
- Documented the current release version.

## 0.0.1 - 2026-05-03

Initial public preview release.

### Added

- Home Assistant config flow with Octopus Spain email/password authentication.
- In-memory Kraken token handling.
- GraphQL client for the observed Octopus Spain Kraken endpoint.
- Safe account/property/ledger selection using hashed identifiers.
- Tariff sensors: product name, product code, validity, energy price, power prices and surplus rate.
- Sun Club window binary sensor and current energy price estimate.
- Billing and invoice entities with redacted invoice references.
- Response services:
  - `octopus_spain.get_invoice_document`
  - `octopus_spain.get_invoices`
  - `octopus_spain.get_measurements`
- Consumption sensors for the latest complete available day, last 7 days and last 31 days.
- API cost sensor when Octopus exposes measurement cost.
- Estimated energy-only cost sensors derived from hourly consumption, tariff price and regular Sun Club discount.
- Graph-ready attributes for Lovelace/ApexCharts:
  - `series.daily/weekly/monthly/yearly`
  - `period_series.daily/monthly`
  - `hourly_period_series.daily/monthly`
  - `estimated_cost_series_by_date`
- Credit summary sensors and attributes, converting Kraken minor-unit amounts to EUR.
- Safe summaries for devices and referrals.
- Diagnostics redaction helpers.
- Live API probe and smoke-test tools.
- Unit tests for privacy helpers, measurement quality, chart series, translations and scope boundaries.

### Privacy

- Does not expose CUPS, account numbers, ledger numbers, raw property IDs, tokens, cookies, PDFs or signed invoice URLs in entity state/attributes.
- Signed invoice URLs are returned only by explicit response service call.

### Known limitations

- Octopus Spain GraphQL API is private and may change.
- Latest invoice amount/date sensors remain unavailable when `BillingInfo.statementsWithDetails` returns no edges.
- Measurement API cost remains unavailable when `metaData.statistics` is empty; estimated cost sensors are informational and do not include power term, taxes or invoice adjustments.
- Manual account/property selection is not implemented yet.
