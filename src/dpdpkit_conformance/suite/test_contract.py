"""The REST contract. Every adapter and dpdpkit-server must pass all of these before release."""

from __future__ import annotations

import io
import zipfile
from typing import Any

import httpx

from dpdpkit_conformance import assert_schema

from .conftest import admin, assert_error, user


def _grant(client: httpx.Client, principal: str, purpose: str) -> httpx.Response:
    return client.post(
        "/consents", json={"decisions": [{"purpose": purpose, "granted": True}]}, headers=user(principal)
    )


# --------------------------------------------------------------------------- notices


def test_notice_has_required_links_and_itemised_purposes(notice: dict[str, Any]) -> None:
    for link in ("withdraw", "rights", "board_complaint"):
        assert notice["links"].get(link), f"notice is missing the {link} link"
    assert notice["purposes"], "notice must itemise at least one purpose"
    for p in notice["purposes"]:
        assert p["data_items"], f"purpose {p['id']} lists no data items"


def test_notice_locale_falls_back(client: httpx.Client, notice: dict[str, Any]) -> None:
    resp = client.get("/notices/current", params={"locale": "zz-ZZ"})
    assert resp.status_code == 200
    assert resp.json()["version"] == notice["version"]
    assert resp.json()["locale"] in notice["available_locales"]


# --------------------------------------------------------------------------- consent


def test_unauthenticated_calls_are_refused(client: httpx.Client) -> None:
    assert_error(client.get("/consents/me"), 401, "unauthenticated")


def test_grant_withdraw_roundtrip(client: httpx.Client, principal: str, purpose: str, notice: dict[str, Any]) -> None:
    resp = client.post(
        "/consents",
        json={"notice_version": notice["version"], "decisions": [{"purpose": purpose, "granted": True}]},
        headers=user(principal),
    )
    assert resp.status_code == 201, resp.text
    assert_schema(resp.json(), "ConsentList")
    [state] = resp.json()["consents"]
    assert state["status"] == "granted" and state["notice_version"] == notice["version"]

    mine = client.get("/consents/me", headers=user(principal)).json()
    assert_schema(mine, "ConsentList")
    assert {c["purpose"]: c["status"] for c in mine["consents"]}[purpose] == "granted"

    resp = client.post(f"/consents/{purpose}/withdraw", headers=user(principal))
    assert resp.status_code == 200, resp.text
    assert_schema(resp.json(), "ConsentState")
    assert resp.json()["status"] == "withdrawn"

    assert_error(client.post(f"/consents/{purpose}/withdraw", headers=user(principal)), 409, "invalid_transition")


def test_deny_is_recorded(client: httpx.Client, principal: str, purpose: str) -> None:
    resp = client.post(
        "/consents", json={"decisions": [{"purpose": purpose, "granted": False}]}, headers=user(principal)
    )
    assert resp.status_code == 201
    assert resp.json()["consents"][0]["status"] == "denied"


def test_consent_is_per_principal(client: httpx.Client, principal: str, purpose: str) -> None:
    _grant(client, principal, purpose)
    other = client.get("/consents/me", headers=user(principal + "-other")).json()
    assert other["consents"] == []


def test_unknown_purpose_and_bad_bodies(client: httpx.Client, principal: str) -> None:
    resp = client.post(
        "/consents", json={"decisions": [{"purpose": "no-such-purpose", "granted": True}]}, headers=user(principal)
    )
    assert resp.status_code in (404, 422)
    assert_schema(resp.json(), "Error")
    assert_error(client.post("/consents", json={"decisions": []}, headers=user(principal)), 422)
    assert_error(client.post("/consents/no-such-purpose/withdraw", headers=user(principal)), 404, "not_found")


def test_receipt_is_signed(client: httpx.Client, principal: str, purpose: str) -> None:
    _grant(client, principal, purpose)
    resp = client.get("/consents/me/receipt", headers=user(principal))
    assert resp.status_code == 200
    receipt = resp.json()
    assert_schema(receipt, "ConsentReceipt")
    assert receipt["principal"] == principal
    assert [c["purpose"] for c in receipt["consents"]] == [purpose]


# --------------------------------------------------------------------------- rights requests


def test_open_and_track_request(client: httpx.Client, principal: str) -> None:
    resp = client.post("/requests", json={"kind": "access"}, headers=user(principal))
    assert resp.status_code == 201, resp.text
    req = resp.json()
    assert_schema(req, "RightsRequest")
    assert req["opened_at"] < req["due_at"] <= req["max_due_at"]
    assert req["overdue"] is False

    got = client.get(f"/requests/{req['id']}", headers=user(principal))
    assert got.status_code == 200 and got.json()["id"] == req["id"]
    assert_error(client.get(f"/requests/{req['id']}", headers=user(principal + "-x")), 404, "not_found")

    listed = client.get("/requests", headers=user(principal)).json()
    assert [r["id"] for r in listed["items"]] == [req["id"]]


def test_invalid_request_kind(client: httpx.Client, principal: str) -> None:
    assert_error(client.post("/requests", json={"kind": "teleport"}, headers=user(principal)), 422)


def test_nomination_requires_details(client: httpx.Client, principal: str) -> None:
    assert_error(client.post("/requests", json={"kind": "nomination", "details": {}}, headers=user(principal)), 422)
    resp = client.post(
        "/requests",
        json={"kind": "nomination", "details": {"name": "Asha", "contact": "asha@example.in"}},
        headers=user(principal),
    )
    assert resp.status_code == 201
    assert resp.json()["status"] in ("completed", "identity_pending")


def test_export(client: httpx.Client, principal: str, purpose: str) -> None:
    _grant(client, principal, purpose)
    resp = client.get("/me/export", headers=user(principal))
    assert resp.status_code == 200
    assert_schema(resp.json(), "PrincipalExport")
    assert resp.json()["principal"] == principal
    html = client.get("/me/export", params={"format": "html"}, headers=user(principal))
    assert html.status_code == 200 and html.headers["content-type"].startswith("text/html")


# --------------------------------------------------------------------------- admin


def test_admin_requires_role(client: httpx.Client, principal: str) -> None:
    resp = client.get("/admin/requests", headers=user(principal))
    assert resp.status_code in (401, 403)
    assert_schema(resp.json(), "Error")


def test_admin_request_workflow(client: httpx.Client, principal: str) -> None:
    req = client.post("/requests", json={"kind": "correction", "details": {"field": "name"}}, headers=user(principal))
    rid = req.json()["id"]

    queue = client.get("/admin/requests", params={"open": True}, headers=admin("viewer"))
    assert queue.status_code == 200
    items = {r["id"]: r for r in queue.json()["items"]}
    assert rid in items
    assert_schema(items[rid], "AdminRightsRequest")
    assert items[rid]["principal"] == principal

    assert_error(client.patch(f"/admin/requests/{rid}", json={"action": "start"}, headers=admin("viewer")), 403)

    resp = client.patch(f"/admin/requests/{rid}", json={"action": "assign", "assignee": "h1"}, headers=admin("handler"))
    assert resp.status_code == 200 and resp.json()["assignee"] == "h1"
    if resp.json()["status"] == "identity_pending":
        client.patch(
            f"/admin/requests/{rid}", json={"action": "verify_identity", "verified": True}, headers=admin("handler")
        )
    else:
        resp = client.patch(f"/admin/requests/{rid}", json={"action": "start"}, headers=admin("handler"))
        assert resp.json()["status"] == "in_progress"
    done = client.patch(
        f"/admin/requests/{rid}", json={"action": "respond", "message": "Name corrected."}, headers=admin("handler")
    )
    assert done.status_code == 200, done.text
    body = done.json()
    assert_schema(body, "AdminRightsRequest")
    assert body["status"] == "completed" and body["response_contact"], "responses must carry contact details"

    again = client.patch(f"/admin/requests/{rid}", json={"action": "respond", "message": "x"}, headers=admin("handler"))
    assert_error(again, 409, "invalid_transition")
    assert_error(client.patch("/admin/requests/nope", json={"action": "start"}, headers=admin("handler")), 404)
    assert_error(client.patch(f"/admin/requests/{rid}", json={"action": "fly"}, headers=admin("handler")), 422)


def test_retention_preview(client: httpx.Client) -> None:
    resp = client.get("/admin/retention/preview", params={"hours": 24 * 60}, headers=admin("viewer"))
    assert resp.status_code == 200
    assert_schema(resp.json(), "RetentionPreview")


def test_ledger_verify(client: httpx.Client, principal: str, purpose: str) -> None:
    _grant(client, principal, purpose)
    resp = client.post("/admin/ledger/verify", headers=admin("viewer"))
    assert resp.status_code == 200
    body = resp.json()
    assert_schema(body, "LedgerVerification")
    assert body["ok"] is True and body["checked"] >= 1


def test_audit_export_is_a_zip(client: httpx.Client) -> None:
    assert client.get("/admin/audit/export", headers=admin("handler")).status_code == 403
    resp = client.get("/admin/audit/export", headers=admin("admin"))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/zip")
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        assert "consent_events.csv" in zf.namelist()


def test_activity_signal(client: httpx.Client, principal: str) -> None:
    resp = client.post("/events/activity", json={"principal": principal}, headers=admin("handler"))
    assert resp.status_code == 202 and resp.json() == {"accepted": True}
    assert_error(client.post("/events/activity", json={}, headers=admin("handler")), 422)
    refused = client.post("/events/activity", json={"principal": principal}, headers=user(principal))
    assert refused.status_code in (401, 403)
