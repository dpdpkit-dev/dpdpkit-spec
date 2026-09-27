from __future__ import annotations

import importlib
import os
import sys
import uuid
from collections.abc import Iterator
from typing import Any

import httpx
import pytest

from dpdpkit_conformance import PRINCIPAL_HEADER, ROLE_HEADER, assert_schema


@pytest.fixture(scope="session")
def client() -> Iterator[httpx.Client]:
    prefix = os.environ.get("DPDPKIT_PREFIX", "/dpdp")
    app_spec = os.environ.get("DPDPKIT_ASGI_APP")
    if app_spec:
        from starlette.testclient import TestClient

        sys.path.insert(0, os.getcwd())
        module_name, _, attr = app_spec.partition(":")
        app: Any = importlib.import_module(module_name)
        for part in attr.split("."):
            app = getattr(app, part)
        with TestClient(app, base_url=f"http://testserver{prefix}") as c:
            yield c
        return
    base = os.environ.get("DPDPKIT_BASE_URL")
    if not base:
        pytest.exit("set DPDPKIT_BASE_URL (e.g. http://localhost:8000/dpdp) or DPDPKIT_ASGI_APP", returncode=4)
    with httpx.Client(base_url=base, timeout=30) as c:
        yield c


@pytest.fixture
def principal() -> str:
    return f"conf-{uuid.uuid4().hex[:12]}"


def user(principal: str) -> dict[str, str]:
    return {PRINCIPAL_HEADER: principal}


def admin(role: str = "admin") -> dict[str, str]:
    return {ROLE_HEADER: role, PRINCIPAL_HEADER: f"conf-staff-{role}"}


@pytest.fixture(scope="session")
def notice(client: httpx.Client) -> dict[str, Any]:
    resp = client.get("/notices/current")
    assert resp.status_code == 200, f"app under test must publish a notice before conformance runs: {resp.text}"
    body = resp.json()
    assert_schema(body, "Notice")
    return body  # type: ignore[no-any-return]


@pytest.fixture(scope="session")
def purpose(notice: dict[str, Any]) -> str:
    consent = [p["id"] for p in notice["purposes"] if p["legal_basis"] == "consent"]
    if not consent:
        pytest.skip("the app under test has no consent-based purpose")
    return consent[-1]


def assert_error(resp: httpx.Response, status: int, code: str | None = None) -> None:
    assert resp.status_code == status, f"expected {status}, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert_schema(body, "Error")
    if code:
        assert body["error"]["code"] == code, body
