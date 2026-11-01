"""Self-test of the upgrade helpers against a tiny in-memory fake; no real adapter involved."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from dpdpkit_conformance import PRINCIPAL_HEADER
from dpdpkit_conformance import upgrade as up

NOTICE = {"purposes": [{"id": "marketing", "legal_basis": "consent"}]}


def make_app(db: dict[str, Any]) -> Starlette:
    """``db`` plays the database: it outlives the app, like data across a release upgrade."""

    def who(request: Request) -> str:
        return request.headers[PRINCIPAL_HEADER]

    async def notice(request: Request) -> JSONResponse:
        return JSONResponse(NOTICE)

    async def grant(request: Request) -> JSONResponse:
        body = await request.json()
        p = body["decisions"][0]["purpose"]
        event = {"purpose": p, "status": "granted", "notice_version": 3, "event_id": f"ev-{len(db['ledger'])}"}
        db["consents"].setdefault(who(request), {})[p] = event
        db["ledger"].append(event)
        return JSONResponse({"consents": [event]}, status_code=201)

    async def consents(request: Request) -> JSONResponse:
        return JSONResponse({"consents": list(db["consents"].get(who(request), {}).values())})

    async def receipt(request: Request) -> JSONResponse:
        mine = list(db["consents"].get(who(request), {}).values())
        return JSONResponse({"principal": who(request), "consents": mine})

    async def open_request(request: Request) -> JSONResponse:
        req = {
            "id": f"r{len(db['requests'])}",
            "kind": "access",
            "opened_at": "2027-01-01T00:00:00Z",
            "due_at": "2027-01-15T00:00:00Z",
            "max_due_at": "2027-01-31T00:00:00Z",
        }
        db["requests"][req["id"]] = req
        return JSONResponse(req, status_code=201)

    async def get_request(request: Request) -> JSONResponse:
        req = db["requests"].get(request.path_params["id"])
        return JSONResponse(req, status_code=200 if req else 404)

    async def ledger(request: Request) -> JSONResponse:
        return JSONResponse({"ok": True, "checked": len(db["ledger"])})

    return Starlette(
        routes=[
            Route("/dpdp/notices/current", notice),
            Route("/dpdp/consents", grant, methods=["POST"]),
            Route("/dpdp/consents/me", consents),
            Route("/dpdp/consents/me/receipt", receipt),
            Route("/dpdp/requests", open_request, methods=["POST"]),
            Route("/dpdp/requests/{id}", get_request),
            Route("/dpdp/admin/ledger/verify", ledger, methods=["POST"]),
        ]
    )


def new_db() -> dict[str, Any]:
    return {"consents": {}, "ledger": [], "requests": {}}


def client_for(db: dict[str, Any]) -> httpx.Client:
    return TestClient(make_app(db), base_url="http://testserver/dpdp")


@pytest.fixture(autouse=True)
def _skip_schema_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    # The fake is intentionally minimal; schema conformance is covered by the real suite.
    monkeypatch.setattr(up, "assert_schema", lambda *_a, **_k: None)


def test_seed_then_verify_passes_after_upgrade(tmp_path: Path) -> None:
    db = new_db()
    with client_for(db) as old:
        seeded = up.seed(old)
    json.dumps(seeded)  # state must be serialisable
    with client_for(db) as new:  # new release, same database
        up.verify(new, seeded)


def test_verify_detects_lost_consent() -> None:
    db = new_db()
    with client_for(db) as old:
        seeded = up.seed(old)
    db["consents"].clear()
    with client_for(db) as new, pytest.raises(up.UpgradeError, match="lost"):
        up.verify(new, seeded)


def test_verify_detects_changed_request_deadline() -> None:
    db = new_db()
    with client_for(db) as old:
        seeded = up.seed(old)
    db["requests"][seeded["request"]["id"]]["due_at"] = "2027-02-01T00:00:00Z"
    with client_for(db) as new, pytest.raises(up.UpgradeError, match="due_at"):
        up.verify(new, seeded)


def test_verify_detects_shrunk_ledger() -> None:
    db = new_db()
    with client_for(db) as old:
        seeded = up.seed(old)
    db["ledger"].clear()
    with client_for(db) as new, pytest.raises(up.UpgradeError, match="ledger shrank"):
        up.verify(new, seeded)


def test_cli_usage_error() -> None:
    assert up.main(["bogus"]) == 2
