from __future__ import annotations

from openapi_spec_validator import validate

from dpdpkit_conformance import openapi, schema_errors

CONTRACT = {
    ("get", "/notices/current"),
    ("post", "/consents"),
    ("post", "/consents/{purpose}/withdraw"),
    ("get", "/consents/me"),
    ("get", "/consents/me/receipt"),
    ("post", "/requests"),
    ("get", "/requests/{id}"),
    ("get", "/me/export"),
    ("get", "/admin/requests"),
    ("patch", "/admin/requests/{id}"),
    ("get", "/admin/retention/preview"),
    ("get", "/admin/incidents"),
    ("post", "/admin/incidents"),
    ("get", "/admin/incidents/{id}/report"),
    ("get", "/admin/audit/export"),
    ("post", "/admin/ledger/verify"),
    ("post", "/events/activity"),
}


def test_document_is_valid_openapi_31() -> None:
    doc = openapi()
    assert doc["openapi"].startswith("3.1")
    validate(doc)


def test_every_contract_endpoint_is_specified() -> None:
    paths = openapi()["paths"]
    present = {(m, p) for p, ops in paths.items() for m in ops if m in {"get", "post", "patch", "put", "delete"}}
    assert CONTRACT <= present, sorted(CONTRACT - present)


def test_every_error_response_uses_error_schema() -> None:
    for path, ops in openapi()["paths"].items():
        for method, op in ops.items():
            if not isinstance(op, dict) or "responses" not in op:
                continue
            for status, resp in op["responses"].items():
                if not status.startswith("2"):
                    assert resp == {"$ref": "#/components/responses/Error"}, f"{method} {path} {status}"


def test_schema_validation_helper() -> None:
    good = {"error": {"code": "not_found", "message": "x"}}
    assert schema_errors(good, "Error") == []
    assert schema_errors({"error": {"code": 1}}, "Error")
    state = {
        "purpose": "m",
        "status": "granted",
        "notice_version": 1,
        "updated_at": "2027-01-01T00:00:00Z",
        "event_id": "e",
    }
    assert schema_errors(state, "ConsentState") == []
    assert schema_errors({**state, "status": "maybe"}, "ConsentState")
