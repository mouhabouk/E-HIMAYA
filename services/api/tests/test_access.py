"""Access model (phase 9, docs/api/phase-9-contract.md §1): functions and rooms, the action matrix of the one policy
function, masking of the reporter's identity, technical roles without operational data, and the IDOR suite (ids
and filters of another gouvernorat on the staff routes)."""

import secrets
import uuid
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Ctx, authorize
from app.core.security import Principal, Realm, Role
from tests.conftest import SFAX, TokenFactory, accept_charter, bearer, device_headers, report_body
from tests.test_profile import random_cin

Staff = Callable[..., dict[str, str]]
GABES = 81


# ---------------------------------------------------------------- functions and rooms


def principal(*roles: str, gouvernorat: int | None = 61, subject: str | None = None) -> Principal:
    return Principal(
        subject=subject or str(uuid.uuid4()),
        realm=Realm.STAFF,
        roles=frozenset(Role(r) for r in roles),
        gouvernorat_code=gouvernorat,
    )


def test_functions_and_room_derivation() -> None:
    assert principal("operator").functions == frozenset({"operations"})
    assert principal("operator", "content_editor").functions == frozenset({"operations", "support"})
    assert principal("central_committee", gouvernorat=None).functions == frozenset({"command"})
    assert principal("security_admin", "ai_admin", gouvernorat=None).functions == frozenset({"technical"})
    assert principal("operator").room == "regional"
    assert principal("operator", gouvernorat=None).room == "central"
    citizen = Principal(subject="c", realm=Realm.PUBLIC, roles=frozenset({Role.CITIZEN}))
    assert citizen.functions == frozenset()


# ---------------------------------------------------------------- the matrix (§1.2)

OWN = Ctx(lead=61)
OTHER = Ctx(lead=GABES)
PARTICIPANT = Ctx(lead=GABES, participants=frozenset({GABES, 61}))
LATE = Ctx(lead=61, late=True)
UNVERIFIED = Ctx(lead=None, candidates=frozenset({61, 62}))
CRITICAL_CANDIDATE = Ctx(lead=None, candidates=frozenset({61, 62}), critical=True)
CENTRAL_LEVEL = Ctx(lead=61, command_level="central")
REFERRED_HERE = Ctx(lead=GABES, referred_to=61, late=True)
N = None  # national scope

MATRIX_CASES: list[tuple[str, int | None, Action, Ctx, str]] = [
    # Reads: own room, participants, critical candidates; national always; technical and support never.
    ("operator", 61, Action.REPORT_READ, OWN, "allow"),
    ("operator", 61, Action.REPORT_READ, OTHER, "404"),
    ("operator", 61, Action.INCIDENT_READ, PARTICIPANT, "allow"),
    ("operator", 61, Action.REPORT_READ, CRITICAL_CANDIDATE, "allow"),
    ("operator", 61, Action.REPORT_READ, UNVERIFIED, "404"),
    ("operator", N, Action.REPORT_READ, OTHER, "allow"),
    ("local_committee", 61, Action.REPORT_READ, OWN, "allow"),
    ("field_commander", 61, Action.INCIDENT_READ, OWN, "allow"),
    ("central_committee", N, Action.INCIDENT_READ, OTHER, "allow"),
    ("sysadmin", N, Action.REPORT_READ, OWN, "403 action_not_allowed"),
    ("security_admin", N, Action.INCIDENT_READ, OWN, "403 action_not_allowed"),
    ("ai_admin", N, Action.REPORT_READ, OWN, "403 action_not_allowed"),
    ("regional_account_admin", 61, Action.REPORT_READ, OWN, "403 action_not_allowed"),
    ("org_auditor", N, Action.REPORT_READ, OWN, "403 action_not_allowed"),
    ("content_editor", 61, Action.REPORT_READ, OWN, "403 action_not_allowed"),
    # Claim / status / link: the report's room; the centre only when late, unverified or at central command level.
    ("operator", 61, Action.REPORT_CLAIM, OWN, "allow"),
    ("ops_manager", 61, Action.REPORT_STATUS, OWN, "allow"),
    ("operator", 61, Action.REPORT_CLAIM, CRITICAL_CANDIDATE, "allow"),
    ("operator", N, Action.REPORT_CLAIM, OWN, "403 not_claimable"),
    ("operator", N, Action.REPORT_CLAIM, LATE, "allow"),
    ("operator", N, Action.REPORT_STATUS, UNVERIFIED, "allow"),
    ("ops_manager", N, Action.REPORT_LINK, CENTRAL_LEVEL, "allow"),
    ("field_commander", 61, Action.REPORT_CLAIM, OWN, "403 action_not_allowed"),
    ("local_committee", 61, Action.REPORT_STATUS, OWN, "403 action_not_allowed"),
    ("central_committee", N, Action.REPORT_CLAIM, LATE, "403 action_not_allowed"),
    # Referral and geographic verification: national; the decision belongs to the target room.
    ("operator", N, Action.REPORT_REFER, LATE, "allow"),
    ("central_committee", N, Action.REPORT_GEO_VERIFY, UNVERIFIED, "allow"),
    ("operator", 61, Action.REPORT_REFER, OWN, "403 action_not_allowed"),
    ("ops_manager", 61, Action.REPORT_GEO_VERIFY, CRITICAL_CANDIDATE, "403 action_not_allowed"),
    ("operator", 61, Action.REPORT_REFERRAL_DECIDE, REFERRED_HERE, "allow"),
    ("local_committee", 61, Action.REPORT_REFERRAL_DECIDE, REFERRED_HERE, "allow"),
    ("operator", 61, Action.REPORT_REFERRAL_DECIDE, OWN, "403 action_not_allowed"),
    ("central_committee", N, Action.REPORT_REFERRAL_DECIDE, REFERRED_HERE, "403 action_not_allowed"),
    # Field actions: the region only, never the centre.
    ("operator", 61, Action.INCIDENT_ASSIGN, OWN, "allow"),
    ("field_commander", 61, Action.INCIDENT_CALLOUT, PARTICIPANT, "allow"),
    ("operator", N, Action.INCIDENT_ASSIGN, OWN, "403 field_action_regional_only"),
    ("ops_manager", N, Action.ASSIGNMENT_STATUS, OWN, "403 field_action_regional_only"),
    ("local_committee", 61, Action.INCIDENT_ASSIGN, OWN, "403 action_not_allowed"),
    ("central_committee", N, Action.INCIDENT_ASSIGN, OWN, "403 action_not_allowed"),
    ("operator", 61, Action.INCIDENT_CARD, PARTICIPANT, "allow"),
    ("local_committee", 61, Action.INCIDENT_NOTE, OWN, "403 action_not_allowed"),
    # Closing, participants, merge: the lead room's managers; lead transfer and command level: national.
    ("ops_manager", 61, Action.INCIDENT_CLOSE, OWN, "allow"),
    ("ops_manager", 61, Action.INCIDENT_CLOSE, PARTICIPANT, "403 action_not_allowed"),
    ("operator", 61, Action.INCIDENT_CLOSE, OWN, "403 action_not_allowed"),
    ("ops_manager", 61, Action.INCIDENT_PARTICIPANTS, OWN, "allow"),
    ("local_committee", 61, Action.INCIDENT_PARTICIPANTS, OWN, "allow"),
    ("ops_manager", 61, Action.INCIDENT_PARTICIPANTS, PARTICIPANT, "403 action_not_allowed"),
    ("operator", 61, Action.INCIDENT_MERGE, OWN, "403 action_not_allowed"),
    ("ops_manager", N, Action.INCIDENT_MERGE, OTHER, "allow"),
    ("ops_manager", N, Action.INCIDENT_LEAD_TRANSFER, OTHER, "allow"),
    ("central_committee", N, Action.INCIDENT_COMMAND_LEVEL, OTHER, "allow"),
    ("ops_manager", 61, Action.INCIDENT_LEAD_TRANSFER, OWN, "403 action_not_allowed"),
    # Resource requests: any field room of the incident asks; the owning region decides (or central command).
    ("field_commander", 61, Action.RESOURCE_REQUEST_CREATE, PARTICIPANT, "allow"),
    ("operator", N, Action.RESOURCE_REQUEST_CREATE, OTHER, "allow"),
    ("ops_manager", 61, Action.RESOURCE_REQUEST_DECIDE, OWN, "allow"),
    ("ops_manager", 61, Action.RESOURCE_REQUEST_DECIDE, PARTICIPANT, "403 action_not_allowed"),
    ("central_committee", N, Action.RESOURCE_REQUEST_DECIDE, OWN, "403 action_not_allowed"),
    ("central_committee", N, Action.RESOURCE_REQUEST_DECIDE, CENTRAL_LEVEL, "allow"),
    # Directives: the centre after a late report (ops manager) or always (committee); the governor's committee.
    ("ops_manager", N, Action.DIRECTIVE_ISSUE, LATE, "allow"),
    ("ops_manager", N, Action.DIRECTIVE_ISSUE, OWN, "403 action_not_allowed"),
    ("local_committee", 61, Action.DIRECTIVE_ISSUE, OWN, "allow"),
    ("local_committee", 61, Action.DIRECTIVE_ISSUE, OTHER, "403 action_not_allowed"),
    # National settings, security and audit.
    ("central_committee", N, Action.SETTINGS_WRITE, OWN, "allow"),
    ("central_committee", 61, Action.SETTINGS_WRITE, OWN, "403 national_scope_required"),
    ("ai_admin", N, Action.SETTINGS_WRITE, OWN, "allow"),
    ("operator", N, Action.SETTINGS_WRITE, OWN, "403 action_not_allowed"),
    ("sysadmin", N, Action.SETTINGS_WRITE, OWN, "403 action_not_allowed"),
    ("security_admin", N, Action.BREAKGLASS_REVIEW, OWN, "allow"),
    ("security_admin", 61, Action.BREAKGLASS_REVIEW, OWN, "403 national_scope_required"),
    ("operator", 61, Action.BREAKGLASS_REQUEST, OWN, "allow"),
    ("sysadmin", N, Action.BREAKGLASS_REQUEST, OWN, "403 action_not_allowed"),
    ("security_admin", N, Action.AUDIT_READ_RAW, OWN, "allow"),
    ("sysadmin", N, Action.AUDIT_READ_RAW, OWN, "403 action_not_allowed"),
    ("ops_manager", 61, Action.AUDIT_READ_SCOPED, OWN, "allow"),
    ("operator", 61, Action.AUDIT_READ_SCOPED, OWN, "403 action_not_allowed"),
    # Accounts, units and resources: objects of the caller's own gouvernorat only.
    ("regional_account_admin", 61, Action.ACCOUNT_MANAGE, OWN, "allow"),
    ("regional_account_admin", 61, Action.ACCOUNT_MANAGE, OTHER, "404"),
    ("regional_account_admin", 61, Action.ACCOUNT_MANAGE, PARTICIPANT, "404"),
    ("regional_account_admin", N, Action.ACCOUNT_MANAGE, OTHER, "allow"),
    ("ops_manager", 61, Action.UNITS_WRITE, OWN, "allow"),
    ("ops_manager", 61, Action.RESOURCES_WRITE, OTHER, "404"),
    ("ops_manager", N, Action.RESOURCES_WRITE, OTHER, "allow"),
    ("sysadmin", N, Action.UNITS_WRITE, OWN, "403 action_not_allowed"),
    ("operator", 61, Action.RESOURCES_WRITE, OWN, "403 action_not_allowed"),
]


def outcome(decision: Any) -> str:
    if decision.allowed:
        return "allow"
    return "404" if decision.status_code == 404 else f"{decision.status_code} {decision.code}"


@pytest.mark.parametrize(
    ("role", "gouvernorat", "action", "ctx", "expected"),
    MATRIX_CASES,
    ids=[f"{c[2].value}-{c[0]}-{'N' if c[1] is None else c[1]}-{i}" for i, c in enumerate(MATRIX_CASES)],
)
async def test_matrix(
    session: AsyncSession, role: str, gouvernorat: int | None, action: Action, ctx: Ctx, expected: str
) -> None:
    assert outcome(await authorize(session, principal(role, gouvernorat=gouvernorat), action, ctx)) == expected


async def test_several_roles_take_the_most_permissive(session: AsyncSession) -> None:
    both = principal("content_editor", "operator")
    assert outcome(await authorize(session, both, Action.REPORT_CLAIM, OWN)) == "allow"
    # A technical role never adds operational rights, and does not take them away either.
    mixed = principal("sysadmin", "operator", gouvernorat=None)
    assert outcome(await authorize(session, mixed, Action.INCIDENT_ASSIGN, OWN)) == "403 field_action_regional_only"
    assert outcome(await authorize(session, mixed, Action.REPORT_READ, OTHER)) == "allow"


async def test_reporter_identity_rule(session: AsyncSession) -> None:
    claimed_here = Ctx(lead=61, claimed_room="g:61")
    assert outcome(await authorize(session, principal("operator"), Action.REPORT_READ_SENSITIVE, claimed_here)) == (
        "allow"
    )
    for role in ("field_commander", "local_committee"):
        refused = await authorize(session, principal(role), Action.REPORT_READ_SENSITIVE, claimed_here)
        assert outcome(refused) == "403 action_not_allowed", role
    # Another room, or the centre without the claim: masked; out of scope: not disclosed.
    national = principal("operator", gouvernorat=None)
    assert outcome(await authorize(session, national, Action.REPORT_READ_SENSITIVE, claimed_here)) == (
        "403 action_not_allowed"
    )
    central_claim = Ctx(lead=61, claimed_room="central", late=True)
    assert outcome(await authorize(session, national, Action.REPORT_READ_SENSITIVE, central_claim)) == "allow"
    assert outcome(await authorize(session, principal("operator"), Action.REPORT_READ_SENSITIVE, central_claim)) == (
        "403 action_not_allowed"
    )
    gabes = principal("operator", gouvernorat=GABES)
    assert outcome(await authorize(session, gabes, Action.REPORT_READ_SENSITIVE, claimed_here)) == "404"
    security = principal("security_admin", gouvernorat=None)
    assert outcome(await authorize(session, security, Action.REPORT_READ_SENSITIVE, claimed_here)) == (
        "403 action_not_allowed"
    )


# ---------------------------------------------------------------- over HTTP


async def anonymous_report(client: httpx.AsyncClient, location: dict[str, float], **overrides: Any) -> dict[str, Any]:
    headers = device_headers()
    await accept_charter(client, headers)
    r = await client.post("/api/v1/reports", json=report_body(location, **overrides), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


async def citizen_report(client: httpx.AsyncClient, make_token: TokenFactory, home: int = 34) -> dict[str, Any]:
    """A registered citizen living in ``home`` (Sousse by default) reports a fire in Sfax."""
    headers = bearer(make_token(roles=["citizen"]))
    profile = {
        "first_name": "Sami",
        "last_name": "Gharbi",
        "cin": random_cin(),
        "phone": "+21697000112",
        "gouvernorat_code": home,
        "delegation_id": home * 100 + 1,
        "locale": "fr",
    }
    r = await client.put("/api/v1/me/profile", json=profile, headers=headers)
    assert r.status_code == 200, r.text
    await accept_charter(client, headers)
    r = await client.post("/api/v1/reports", json=report_body(SFAX), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def place() -> dict[str, float]:
    # Inside Sfax, away from the fixed points of other tests (no grouping suggestion, no duplicate guard).
    return {
        "lat": 34.60 + secrets.randbelow(1000) / 10_000,
        "lon": 10.50 + secrets.randbelow(1000) / 10_000,
        "accuracy_m": 10.0,
    }


async def detail(client: httpx.AsyncClient, headers: dict[str, str], report_id: str) -> httpx.Response:
    return await client.get(f"/api/v1/staff/reports/{report_id}", headers=headers)


async def test_technical_roles_no_ops(client: httpx.AsyncClient, staff: Staff) -> None:
    report = await anonymous_report(client, SFAX)
    for role in ("sysadmin", "security_admin", "ai_admin", "regional_account_admin"):
        for gouvernorat in (None, 61):
            headers = staff([role], gouvernorat=gouvernorat)
            assert (await client.get("/api/v1/staff/reports", headers=headers)).status_code == 403, role
            assert (await detail(client, headers, report["id"])).status_code in {403, 404}, role
            assert (await client.get("/api/v1/staff/incidents", headers=headers)).status_code == 403, role
            r = await client.post(f"/api/v1/staff/reports/{report['id']}/claim", headers=headers)
            assert r.status_code in {403, 404}, role


async def test_committee_cannot_triage(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    report = await anonymous_report(client, SFAX)
    for role in ("local_committee", "field_commander"):
        headers = staff([role], gouvernorat=61)
        assert (await detail(client, headers, report["id"])).status_code == 200
        r = await client.post(
            f"/api/v1/staff/reports/{report['id']}/status", json={"status": "in_progress"}, headers=headers
        )
        assert r.status_code == 403, (role, r.text)
        assert (await client.post(f"/api/v1/staff/reports/{report['id']}/claim", headers=headers)).status_code == 403
    row = (
        await session.execute(
            text("SELECT status, claimed_room FROM reports.report WHERE id = :id"), {"id": report["id"]}
        )
    ).one()
    assert (row.status, row.claimed_room) == ("received", None)


async def test_reporter_masked_unless_handling_room(
    client: httpx.AsyncClient, make_token: TokenFactory, staff: Staff
) -> None:
    report = await citizen_report(client, make_token, home=34)
    viewers = {
        "national operator": staff(gouvernorat=None),
        "central committee": staff(["central_committee"], gouvernorat=None),
        "local committee": staff(["local_committee"], gouvernorat=61),
        "field commander": staff(["field_commander"], gouvernorat=61),
        "sfax operator before the claim": staff(gouvernorat=61),
    }
    for who, headers in viewers.items():
        body = (await detail(client, headers, report["id"])).json()
        assert body["reporter"] == {
            "kind": "citizen",
            "masked": True,
            "first_name": None,
            "last_name": None,
            "phone": "+216••••••12",
        }, who
        assert body["reporter_context"] is None, who
    sfax = staff(gouvernorat=61)
    assert (await client.post(f"/api/v1/staff/reports/{report['id']}/claim", headers=sfax)).status_code == 200
    body = (await detail(client, staff(["ops_manager"], gouvernorat=61), report["id"])).json()
    assert body["reporter"]["masked"] is False
    assert (body["reporter"]["first_name"], body["reporter"]["phone"]) == ("Sami", "+21697000112")
    # The reporter's residence (Sousse) is a contact detail of the handling room, never the jurisdiction.
    assert body["reporter_context"] == {"reporter_gouvernorat_code": 34, "source": "profile"}
    assert body["gouvernorat_code"] == 61
    # Still masked for everyone outside the handling room.
    assert (await detail(client, viewers["national operator"], report["id"])).json()["reporter"]["masked"] is True
    assert (await detail(client, viewers["local committee"], report["id"])).json()["reporter"]["masked"] is True


async def test_national_reads_all_masked_reporter(
    client: httpx.AsyncClient, make_token: TokenFactory, staff: Staff
) -> None:
    sfax_report = await citizen_report(client, make_token)
    national = staff(["central_committee"], gouvernorat=None)
    r = await client.get("/api/v1/staff/reports", params={"limit": 500}, headers=national)
    assert r.status_code == 200
    assert sfax_report["id"] in {i["id"] for i in r.json()["items"]}
    body = (await detail(client, national, sfax_report["id"])).json()
    assert body["reporter"]["masked"] is True and body["reporter"]["first_name"] is None


async def test_reveal_with_grant_is_audited(
    client: httpx.AsyncClient, make_token: TokenFactory, staff: Staff, session: AsyncSession
) -> None:
    report = await citizen_report(client, make_token)
    subject = str(uuid.uuid4())
    gabes = staff(gouvernorat=GABES, sub=subject, name="Amel Gabès")
    assert (await detail(client, gabes, report["id"])).status_code == 404
    r = await client.post(
        "/api/v1/staff/break-glass",
        json={
            "target_kind": "report",
            "target_id": report["id"],
            "justification": "Appel de la victime transféré depuis Gabès, identification urgente.",
            "duration_min": 15,
        },
        headers=gabes,
    )
    assert r.status_code == 201, r.text
    grant_id = r.json()["id"]
    body = (await detail(client, gabes, report["id"])).json()
    assert body["reporter"]["masked"] is False and body["reporter"]["last_name"] == "Gharbi"
    audited = (
        await session.execute(
            text(
                "SELECT actor, details FROM audit.log WHERE action = 'report.view_sensitive' AND target = :t "
                "ORDER BY seq DESC LIMIT 1"
            ),
            {"t": f"report:{report['id']}"},
        )
    ).one()
    assert audited.details["grant_id"] == grant_id
    # Read-only: the grant never allows a write.
    r = await client.post(f"/api/v1/staff/reports/{report['id']}/claim", headers=gabes)
    assert r.status_code in {403, 404}
    r = await client.post(f"/api/v1/staff/reports/{report['id']}/status", json={"status": "in_progress"}, headers=gabes)
    # An unclaimed report needs a claim first (§4.3), which the grant cannot give.
    assert (r.status_code, r.json()["detail"]) == (409, "claim_required")
    row = (
        await session.execute(
            text("SELECT status, claimed_room FROM reports.report WHERE id = :id"), {"id": report["id"]}
        )
    ).one()
    assert (row.status, row.claimed_room) == ("received", None)


# ---------------------------------------------------------------- IDOR suite (§12, criterion 19)


async def sfax_incident(client: httpx.AsyncClient, staff: Staff) -> tuple[str, str]:
    report = await anonymous_report(client, place())
    r = await client.post(
        f"/api/v1/staff/reports/{report['id']}/incident",
        json={"action": "new", "override_reason": "independent test incident"},
        headers=staff(gouvernorat=61),
    )
    assert r.status_code == 200, r.text
    return r.json()["incident_id"], report["id"]


async def snapshot(session: AsyncSession, report_id: str, incident_id: str) -> tuple[Any, ...]:
    report = (
        await session.execute(
            text(
                "SELECT status, claimed_room, incident_id, escalation_state, gouvernorat_code, updated_at "
                "FROM reports.report WHERE id = :id"
            ),
            {"id": report_id},
        )
    ).one()
    incident = (
        await session.execute(
            text(
                "SELECT status, gouvernorat_code, command_level, updated_at, "
                "(SELECT count(*) FROM ops.timeline_event t WHERE t.incident_id = i.id) AS events, "
                "(SELECT count(*) FROM ops.incident_gouvernorat g WHERE g.incident_id = i.id) AS gouvernorats "
                "FROM ops.incident i WHERE id = :id"
            ),
            {"id": incident_id},
        )
    ).one()
    return tuple(report) + tuple(incident)


REASON = {"reason": "tentative hors périmètre"}


def idor_requests(report_id: str, incident_id: str) -> list[tuple[str, str, dict[str, Any] | None]]:
    r, i = f"/api/v1/staff/reports/{report_id}", f"/api/v1/staff/incidents/{incident_id}"
    return [
        ("GET", r, None),
        ("POST", f"{r}/claim", None),
        ("DELETE", f"{r}/claim", REASON),
        ("POST", f"{r}/status", {"status": "in_progress"}),
        ("POST", f"{r}/incident", {"action": "new", "override_reason": "tentative hors périmètre"}),
        ("DELETE", f"{r}/incident", None),
        ("GET", f"{r}/nearby-incidents", None),
        ("POST", f"{r}/suggestion/dismiss", None),
        ("POST", f"{r}/referral/accept", {"note": "x"}),
        ("POST", f"{r}/referral/refuse", REASON),
        ("GET", i, None),
        ("PATCH", i, {"title": "Titre modifié"}),
        ("POST", f"{i}/notes", {"text": "note hors périmètre"}),
        ("POST", f"{i}/close", {"outcome": "resolved", "summary": "Clôture hors périmètre"}),
        ("POST", f"{i}/participants", {"gouvernorat_code": GABES, **REASON}),
        ("DELETE", f"{i}/participants/61", REASON),
        ("POST", f"{i}/merge", {"incident_id": str(uuid.uuid4())}),
        ("POST", f"{i}/assignments", {"resource_id": str(uuid.uuid4())}),
        ("POST", f"{i}/callouts", {"skill": "first_aid", "requested": 1}),
        (
            "POST",
            f"{i}/resource-requests",
            {"to_gouvernorat_code": GABES, "resource_kind": "fire_engine", "quantity": 1, **REASON},
        ),
        ("GET", f"{i}/recommendations", None),
        ("GET", f"{i}/responders", None),
        ("GET", f"{i}/volunteer-suggestions", None),
        ("GET", f"{i}/forecasts", None),
        ("GET", f"{i}/conferences", None),
        ("POST", f"/api/v1/staff/memory/from-incident/{incident_id}", None),
    ]


@pytest.mark.parametrize("role", ["operator", "ops_manager", "field_commander", "local_committee"])
async def test_idor_ids_of_another_gouvernorat(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession, role: str
) -> None:
    incident_id, report_id = await sfax_incident(client, staff)
    before = await snapshot(session, report_id, incident_id)
    gabes = staff([role], gouvernorat=GABES)
    for method, url, body in idor_requests(report_id, incident_id):
        r = await client.request(method, url, json=body, headers=gabes)
        # 404 for the object; a role that may never do this anywhere is stopped first by the role gate, whose answer
        # does not depend on the id (nothing is disclosed either way).
        assert r.status_code == 404 or (r.status_code, r.json()["detail"]) == (403, "insufficient_role"), (
            role,
            method,
            url,
            r.status_code,
            r.text,
        )
    await session.rollback()
    assert await snapshot(session, report_id, incident_id) == before


async def test_idor_list_parameters(client: httpx.AsyncClient, staff: Staff) -> None:
    incident_id, report_id = await sfax_incident(client, staff)
    gabes = staff(gouvernorat=GABES)
    for url, params, item in (
        ("/api/v1/staff/reports", {"gouvernorat": 61, "limit": 500}, report_id),
        ("/api/v1/staff/incidents", {"gouvernorat": 61, "limit": 200}, incident_id),
    ):
        r = await client.get(url, params=params, headers=gabes)
        if r.status_code == 200:
            assert item not in {i["id"] for i in r.json()["items"]}, url
        else:
            assert r.status_code in {403, 404}, (url, r.text)
    r = await client.get(
        "/api/v1/staff/units", params={"gouvernorat": 61}, headers=staff(["ops_manager"], gouvernorat=GABES)
    )
    if r.status_code == 200:
        items = r.json()["items"] if isinstance(r.json(), dict) else r.json()
        assert all(u["gouvernorat_code"] == GABES for u in items)
    else:
        assert r.status_code in {403, 404}


async def test_regional_404_other_gouvernorat(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    """Units and resources: another gouvernorat's ids answer 404 and nothing changes (criterion 9)."""
    manager = staff(["ops_manager"], gouvernorat=61)
    r = await client.post(
        "/api/v1/staff/units",
        json={
            "name_ar": "وحدة صفاقس",
            "name_fr": "Unité de Sfax",
            "kind": "unit",
            "gouvernorat_code": 61,
            "location": {"lat": 34.74, "lon": 10.76},
            "phone": "74 000 000",
        },
        headers=manager,
    )
    assert r.status_code == 201, r.text
    unit = r.json()
    r = await client.post(
        "/api/v1/staff/resources",
        json={"unit_id": unit["id"], "kind": "fire_engine", "label": f"FPT-{secrets.token_hex(3)}"},
        headers=manager,
    )
    assert r.status_code == 201, r.text
    resource = r.json()
    gabes = staff(["ops_manager"], gouvernorat=GABES)
    assert (
        await client.put(f"/api/v1/staff/units/{unit['id']}", json={**unit, "phone": "75 000 000"}, headers=gabes)
    ).status_code == 404
    assert (await client.delete(f"/api/v1/staff/units/{unit['id']}", headers=gabes)).status_code == 404
    changed = {"unit_id": unit["id"], "kind": "fire_engine", "label": "volé"}
    r = await client.put(f"/api/v1/staff/resources/{resource['id']}", json=changed, headers=gabes)
    assert r.status_code == 404
    assert (await client.delete(f"/api/v1/staff/resources/{resource['id']}", headers=gabes)).status_code == 404
    # Creating in another gouvernorat by editing the body is refused too.
    r = await client.post("/api/v1/staff/units", json={**unit, "name_fr": "Faux"}, headers=gabes)
    assert r.status_code in {403, 404}
    row = (
        await session.execute(
            text("SELECT u.phone, r.label FROM ops.unit u JOIN ops.resource r ON r.unit_id = u.id WHERE r.id = :id"),
            {"id": resource["id"]},
        )
    ).one()
    assert (row.phone, row.label) == ("74 000 000", resource["label"])
    # Sysadmin no longer writes logistics (phase 9).
    sysadmin = staff(["sysadmin"], gouvernorat=None)
    r = await client.put(
        f"/api/v1/staff/resources/{resource['id']}", json={**changed, "label": "admin"}, headers=sysadmin
    )
    assert r.status_code == 403
