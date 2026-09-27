# dpdpkit-spec

The single REST contract for [dpdpkit](https://github.com/dpdpkit-dev). The FastAPI adapter, the Django
adapter, `dpdpkit-server` and dpdpkit Cloud all expose exactly this API. The conformance suite here
decides whether an adapter can be released.

> **Disclaimer.** dpdpkit is software that helps you implement obligations under India's Digital Personal
> Data Protection Act, 2023 and the DPDP Rules, 2025. It does not provide legal advice and does not
> guarantee compliance.

- [`openapi.yaml`](openapi.yaml): OpenAPI 3.1, the source of truth. `@dpdpkit/client` generates its types from it.
- `dpdpkit-conformance`: black-box pytest suite (`src/dpdpkit_conformance/suite`).

## Running the conformance suite

```bash
pip install "dpdpkit-conformance[asgi] @ git+https://github.com/dpdpkit-dev/dpdpkit-spec@main"

# against a running server
DPDPKIT_BASE_URL=http://localhost:8000/dpdp dpdpkit-conformance

# in-process against an ASGI app (FastAPI, dpdpkit-server)
DPDPKIT_ASGI_APP=app:app DPDPKIT_PREFIX=/dpdp dpdpkit-conformance
```

### What the app under test must do

1. Publish a notice with at least one consent-based purpose.
2. **Conformance mode:** resolve the principal from the `X-DPDP-Test-Principal` header and the admin role
   (`viewer`, `handler`, `admin`) from `X-DPDP-Test-Role`. Enable this only in test configuration.
3. Register at least one erasure handler (the suite does not trigger erasure, but a production-like setup should).

Any adapter that fails the suite is not released (release-train rule).

## Changing the contract

- Additive changes (new optional field, new endpoint) are minor releases.
- Removing or renaming anything is a breaking change: bump the major version and deprecate first.
- Every change updates the conformance suite in the same pull request.

## Licence

Apache-2.0.
