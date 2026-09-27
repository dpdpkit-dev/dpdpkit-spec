# Changelog

## Unreleased

### Added
- OpenAPI 3.1 contract: notices, consents, receipts, rights requests, principal export, admin request
  queue, retention preview, audit export, ledger verification, activity signals. Incident endpoints
  are specified and marked `x-dpdpkit-phase: 2`.
- Beyond the original plan table: `GET /requests` (principal's own requests) and `GET /admin/requests/{id}`.
- `dpdpkit-conformance` black-box suite with response validation against the component schemas.
