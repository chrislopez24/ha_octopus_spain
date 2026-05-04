# Changelog

## 0.0.10 - 2026-05-04

Hour-aligned polling release.

### Changed

- Refresh Octopus data on Europe/Madrid whole-hour boundaries instead of one-hour intervals relative to Home Assistant startup.
- Keep the initial startup refresh immediate, then schedule subsequent refreshes for the next `HH:00:00`.

### Fixed

- Update time-derived Sun Club pricing at the correct wall-clock boundary instead of potentially up to an hour late after a restart.

## 0.0.9 - 2026-05-04

Kraken token refresh release.

### Fixed

- Request and keep Kraken refresh tokens in memory so hourly polling can renew the JWT before its one-hour expiry without falling back to email/password every time.
- Decode the JWT expiry claim and proactively refresh five minutes before expiry.
- Treat upstream JWT/authentication GraphQL errors as retryable authentication failures, clearing the stale token and retrying once.
- Serialize concurrent token renewal with a lock to avoid duplicate refresh attempts.

## 0.0.8 - 2026-05-03

Invoice card signed-path release.

### Fixed

- Sign the invoice download API path with Home Assistant `auth/sign_path` before fetching the PDF from the Lovelace card, avoiding unauthenticated browser requests that return 401.
- Resolve invoice downloads against the configured Octopus runtime that owns the requested invoice hash instead of assuming the first loaded config entry.

## 0.0.7 - 2026-05-03

Invoice card authentication release.

### Fixed

- Use Home Assistant's authenticated frontend fetch helper when the card calls the invoice download API endpoint.
- Show the HTTP status in the card error message when PDF generation fails.

## 0.0.6 - 2026-05-03

Invoice download reliability release.

### Fixed

- Always request a fresh signed Octopus PDF URL when downloading an invoice instead of reusing an in-memory signed URL that may have expired.
- Validate that the upstream response starts as a PDF before streaming it to the browser.
- Handle card download errors with a Home Assistant notification instead of letting the browser save an error response as `.txt`.

## 0.0.5 - 2026-05-03

Invoice download card release.

### Added

- Bundled `custom:octopus-invoice-card` Lovelace card served by the integration.
- Authenticated invoice download endpoint at `/api/octopus_spain/invoice/{invoice_id_hash}`.

### Changed

- Invoice PDFs are proxied through Home Assistant as attachments so clicking an invoice row downloads the file instead of exposing a signed Octopus URL to Lovelace.

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
