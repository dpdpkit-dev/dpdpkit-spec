# Changelog

## Unreleased

### Added
- Breaking-change check (oasdiff) on pull requests that touch `openapi.yaml`; override with the
  `breaking-change` label.
- Upgrade tests: `dpdpkit-conformance upgrade seed --state FILE` records consent, request and ledger data on the
  previous release; after migrating, `upgrade verify --state FILE` checks it survived unchanged and re-runs the
  full suite (`--no-suite` to skip).

## 0.1.0a1 - 2026-09-27

### Added
- OpenAPI 3.1 contract: notices, consents, receipts, rights requests, principal export, admin request
  queue, retention preview, audit export, ledger verification, activity signals. Incident endpoints
  are specified and marked `x-dpdpkit-phase: 2`.
- Beyond the original plan table: `GET /requests` (principal's own requests) and `GET /admin/requests/{id}`.
- `dpdpkit-conformance` black-box suite with response validation against the component schemas.
