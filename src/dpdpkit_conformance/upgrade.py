"""Upgrade tests: seed data on the previous release, migrate, then verify nothing was lost.

Typical flow (the migration itself is the adapter's own step)::

    dpdpkit-conformance upgrade seed --state seed.json     # app on the previous release
    <install the new release and run its migrations>
    dpdpkit-conformance upgrade verify --state seed.json   # checks the data, then re-runs the suite
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import httpx

from dpdpkit_conformance import PRINCIPAL_HEADER, ROLE_HEADER, assert_schema

STATE_VERSION = 1


class UpgradeError(AssertionError):
    """Data seeded before the upgrade is missing or changed afterwards."""


@contextmanager
def open_client() -> Iterator[httpx.Client]:
    """Client for DPDPKIT_ASGI_APP (in-process) or DPDPKIT_BASE_URL (live server)."""
    import importlib

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
        raise SystemExit("set DPDPKIT_BASE_URL (e.g. http://localhost:8000/dpdp) or DPDPKIT_ASGI_APP")
    with httpx.Client(base_url=base, timeout=30) as c:
        yield c


def _ok(resp: httpx.Response, status: int, what: str) -> Any:
    if resp.status_code != status:
        raise UpgradeError(f"{what}: expected {status}, got {resp.status_code}: {resp.text}")
    return resp.json()


def seed(client: httpx.Client) -> dict[str, Any]:
    """Create a granted consent and an open rights request; return what verify() must find again."""
    notice = _ok(client.get("/notices/current"), 200, "current notice")
    consent = [p["id"] for p in notice["purposes"] if p["legal_basis"] == "consent"]
    if not consent:
        raise UpgradeError("the app under test has no consent-based purpose to seed")
    purpose = consent[-1]
    principal = f"upgrade-{uuid.uuid4().hex[:12]}"
    headers = {PRINCIPAL_HEADER: principal}

    granted = _ok(
        client.post("/consents", json={"decisions": [{"purpose": purpose, "granted": True}]}, headers=headers),
        201,
        "grant consent",
    )
    [state] = granted["consents"]
    request = _ok(client.post("/requests", json={"kind": "access"}, headers=headers), 201, "open request")
    ledger = _ok(
        client.post("/admin/ledger/verify", headers={ROLE_HEADER: "viewer", PRINCIPAL_HEADER: "upgrade-staff"}),
        200,
        "verify ledger",
    )
    return {
        "state_version": STATE_VERSION,
        "principal": principal,
        "purpose": purpose,
        "notice_version": state["notice_version"],
        "consent_event_id": state["event_id"],
        "request": {k: request[k] for k in ("id", "kind", "opened_at", "due_at", "max_due_at")},
        "ledger_checked": ledger["checked"],
    }


def verify(client: httpx.Client, seeded: dict[str, Any]) -> None:
    """Raise UpgradeError unless everything recorded by seed() survived the migration unchanged."""
    if seeded.get("state_version") != STATE_VERSION:
        raise UpgradeError(f"unsupported seed state version: {seeded.get('state_version')}")
    headers = {PRINCIPAL_HEADER: seeded["principal"]}
    purpose = seeded["purpose"]

    mine = _ok(client.get("/consents/me", headers=headers), 200, "list consents")
    assert_schema(mine, "ConsentList")
    states = {c["purpose"]: c for c in mine["consents"]}
    if purpose not in states:
        raise UpgradeError(f"consent for {purpose!r} was lost in the upgrade")
    state = states[purpose]
    for field, key in (("status", None), ("notice_version", "notice_version"), ("event_id", "consent_event_id")):
        expected = "granted" if field == "status" else seeded[key or field]
        if state[field] != expected:
            raise UpgradeError(f"consent {field} changed in the upgrade: {expected!r} -> {state[field]!r}")

    receipt = _ok(client.get("/consents/me/receipt", headers=headers), 200, "consent receipt")
    assert_schema(receipt, "ConsentReceipt")
    if receipt["principal"] != seeded["principal"] or [c["purpose"] for c in receipt["consents"]] != [purpose]:
        raise UpgradeError("consent receipt no longer matches the seeded consent")

    seeded_req = seeded["request"]
    req = _ok(client.get(f"/requests/{seeded_req['id']}", headers=headers), 200, "fetch seeded request")
    assert_schema(req, "RightsRequest")
    for key, value in seeded_req.items():
        if req[key] != value:
            raise UpgradeError(f"request {key} changed in the upgrade: {value!r} -> {req[key]!r}")

    ledger = _ok(
        client.post("/admin/ledger/verify", headers={ROLE_HEADER: "viewer", PRINCIPAL_HEADER: "upgrade-staff"}),
        200,
        "verify ledger",
    )
    assert_schema(ledger, "LedgerVerification")
    if not ledger["ok"]:
        raise UpgradeError(f"ledger no longer verifies after the upgrade: {ledger}")
    if ledger["checked"] < seeded["ledger_checked"]:
        raise UpgradeError(f"ledger shrank in the upgrade: {seeded['ledger_checked']} -> {ledger['checked']} rows")


def main(argv: Sequence[str]) -> int:
    """``upgrade seed|verify --state FILE [--no-suite]``; ``verify`` then re-runs the full suite."""
    args = list(argv)
    if len(args) < 3 or args[0] not in ("seed", "verify") or args[1] != "--state":
        usage = "usage: dpdpkit-conformance upgrade (seed|verify) --state FILE [--no-suite] [pytest args]"
        print(usage, file=sys.stderr)
        return 2
    command, path, rest = args[0], Path(args[2]), args[3:]
    run_suite = "--no-suite" not in rest
    rest = [a for a in rest if a != "--no-suite"]

    with open_client() as client:
        if command == "seed":
            path.write_text(json.dumps(seed(client), indent=2) + "\n", encoding="utf-8")
            print(f"seeded; state written to {path}")
            return 0
        try:
            verify(client, json.loads(path.read_text(encoding="utf-8")))
        except UpgradeError as exc:
            print(f"upgrade check failed: {exc}", file=sys.stderr)
            return 1
    print("upgrade check passed: seeded data survived the migration")
    if not run_suite:
        return 0
    import pytest

    return int(pytest.main(["--pyargs", "dpdpkit_conformance.suite", "-p", "no:cacheprovider", *rest]))
