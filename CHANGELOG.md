# Changelog

## Unreleased

## 0.1.0a2 - 2026-11-02

### Added
- `GET /admin/consent/stats` (viewer role) with the `ConsentStats` schema, and a conformance test for it: grants,
  denials and withdrawals per purpose and notice version, for the admin dashboard. Additive.
- Conformance tests for the incident endpoints (register, 72-hour Board and 6-hour CERT-In clocks, draft report,
  roles) and the new guardian endpoints. They skip while the app under test answers `501 not_implemented`.
- `POST /guardian/verify/start` and `POST /guardian/verify/callback` (marked `x-dpdpkit-phase: 2`) with the
  `GuardianVerification` schema. Additive; no existing operation changes.
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
