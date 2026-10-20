"""Access policy: who may do what on which object (phase 9, docs/api/phase-9-contract.md §1).

Every staff read and write goes through ``authorize`` once the object is loaded, before any change. The decision
combines the caller's roles (grouped in functions, ``core.security.FUNCTION_ROLES``), the caller's room (central =
national scope, or one gouvernorat) and what is known about the object (``Ctx``): its lead gouvernorat, the
gouvernorats participating in its incident, the candidate gouvernorats of a report whose location is not trusted
yet, which room claimed it, and whether it is critical or late.

* Out of scope → ``404 not_found`` (existence not disclosed); in scope but not allowed → ``403 <code>``.
* Break-glass grants (``modules.access.grants``) only extend reading: ``report.read``, ``incident.read`` and
  ``report.read_sensitive`` on their target; they never allow a write or a command.
* PostgreSQL row-level security is the second layer: ``db_scope`` carries the request's scope to the database
  session (``core.db``), set by ``security.get_principal`` for staff and ``identity.get_reporter`` for reporters.
"""

import uuid
from contextvars import Token
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, ClassVar, Literal, Protocol

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import NO_SCOPE, SYSTEM_SCOPE, DbScope, db_scope
from app.core.security import Function, Principal, Role

ACTION_NOT_ALLOWED = "action_not_allowed"
NATIONAL_SCOPE_REQUIRED = "national_scope_required"
FIELD_ACTION_REGIONAL_ONLY = "field_action_regional_only"
NOT_CLAIMABLE = "not_claimable"
CENTRAL_ROOM = "central"


class Action(StrEnum):
    REPORT_READ = "report.read"
    INCIDENT_READ = "incident.read"
    REPORT_READ_SENSITIVE = "report.read_sensitive"
    REPORT_CLAIM = "report.claim"
    REPORT_STATUS = "report.status"
    REPORT_LINK = "report.link"
    REPORT_REFER = "report.refer"
    REPORT_GEO_VERIFY = "report.geo_verify"
    REPORT_REFERRAL_DECIDE = "report.referral_decide"
    INCIDENT_CARD = "incident.card"
    INCIDENT_NOTE = "incident.note"
    INCIDENT_ASSIGN = "incident.assign"
    INCIDENT_CALLOUT = "incident.callout"
    ASSIGNMENT_STATUS = "assignment.status"
    INCIDENT_CLOSE = "incident.close"
    INCIDENT_PARTICIPANTS = "incident.participants"
    INCIDENT_MERGE = "incident.merge"
    INCIDENT_LEAD_TRANSFER = "incident.lead_transfer"
    INCIDENT_COMMAND_LEVEL = "incident.command_level"
    RESOURCE_REQUEST_CREATE = "resource_request.create"
    RESOURCE_REQUEST_DECIDE = "resource_request.decide"
    DIRECTIVE_ISSUE = "directive.issue"
    SETTINGS_WRITE = "settings.write"
    BREAKGLASS_REQUEST = "breakglass.request"
    BREAKGLASS_REVIEW = "breakglass.review"
    AUDIT_READ_RAW = "audit.read_raw"
    AUDIT_READ_SCOPED = "audit.read_scoped"
    ACCOUNT_MANAGE = "account.manage"
    UNITS_WRITE = "units.write"
    RESOURCES_WRITE = "resources.write"


@dataclass(frozen=True, slots=True)
class Ctx:
    """What is being touched. Build it from the loaded object (``reports.service.report_ctx``, ops for incidents).

    * ``lead``: the report's ``gouvernorat_code`` or the incident's lead; ``None`` = location not verified (central).
      For ``resource_request.decide`` the owning gouvernorat (``to_gouvernorat_code``); for ``units.write``,
      ``resources.write``, ``account.manage`` and ``directive.issue`` the gouvernorat of the object.
    * ``participants``: gouvernorats of the incident (lead and participating); empty for a lone report.
    * ``candidates``: candidate gouvernorats of a report whose location is pending or contradictory (§4.2).
    * ``claimed_room``: ``"central"`` | ``"g:<code>"`` | ``None``.
    * ``report_id`` / ``incident_id`` / ``referred_to``: optional, let break-glass grants and the referral target
      (§4.4) be recognised.
    """

    lead: int | None
    participants: frozenset[int] = frozenset()
    candidates: frozenset[int] = frozenset()
    claimed_room: str | None = None
    critical: bool = False
    command_level: str = "regional"
    late: bool = False
    report_id: uuid.UUID | None = None
    incident_id: uuid.UUID | None = None
    referred_to: int | None = None


@dataclass(frozen=True, slots=True)
class Decision:
    allowed: bool
    status_code: int = status.HTTP_200_OK
    code: str | None = None
    # Set when the object is readable only through a break-glass grant: the reveal is audited with it.
    grant_id: uuid.UUID | None = None

    allow: ClassVar["Decision"]
    not_found: ClassVar["Decision"]

    @staticmethod
    def forbidden(code: str = ACTION_NOT_ALLOWED) -> "Decision":
        return Decision(False, status.HTTP_403_FORBIDDEN, code)

    @staticmethod
    def through_grant(grant_id: uuid.UUID) -> "Decision":
        return Decision(True, grant_id=grant_id)


Decision.allow = Decision(True)
Decision.not_found = Decision(False, status.HTTP_404_NOT_FOUND, "not_found")


def require(decision: Decision) -> None:
    """Raise ``404 not_found`` or ``403 <code>`` unless the decision allows."""
    if not decision.allowed:
        raise HTTPException(decision.status_code, decision.code)


class ApiError(HTTPException):
    """An error answered as ``{"detail": <code>, **extra}`` (e.g. ``409 already_claimed`` names the claiming room).

    Rendered by the handler registered in ``app.main``."""

    def __init__(self, status_code: int, detail: str, **extra: Any) -> None:
        super().__init__(status_code, detail)
        self.extra = extra


# ---------------------------------------------------------------- rooms and the matrix


def room_of(principal: Principal) -> str:
    """The caller's room as stored on objects: ``central`` or ``g:<code>``."""
    return CENTRAL_ROOM if principal.is_national else f"g:{principal.gouvernorat_code}"


def room_code(room: str | None) -> int | None:
    """Gouvernorat of a ``g:<code>`` room; ``None`` for the central room or no room."""
    return int(room[2:]) if room and room.startswith("g:") else None


# Regional rule: where a regional room may act.  "sees" = any object it can read; "report" = the report's lead room,
# a candidate room of a critical report or the claiming room; "incident" = lead or participating; "lead" = lead
# only; "target" = the room a report was referred to; "any" = no object (the caller's own gouvernorat).
Regional = Literal["sees", "report", "incident", "lead", "target", "any"] | None
# National rule: "always"; "report" = late, unverified location or incident at central command level; "late";
# "central_level" = incident at central command level; "field" = refused as a field action.
National = Literal["always", "report", "late", "central_level", "field"] | None
Rule = tuple[Regional, National]

_OPS = (Role.OPERATOR, Role.OPS_MANAGER)
_FIELD = (Role.OPERATOR, Role.OPS_MANAGER, Role.FIELD_COMMANDER)
_REQUESTERS = (Role.OPERATOR, Role.OPS_MANAGER, Role.FIELD_COMMANDER, Role.LOCAL_COMMITTEE)


def _rules(entries: list[tuple[tuple[Role, ...], Rule]]) -> dict[Role, Rule]:
    return {role: rule for roles, rule in entries for role in roles}


MATRIX: dict[Action, dict[Role, Rule]] = {
    Action.REPORT_READ: _rules([(_REQUESTERS, ("sees", "always")), ((Role.CENTRAL_COMMITTEE,), (None, "always"))]),
    Action.INCIDENT_READ: _rules([(_REQUESTERS, ("sees", "always")), ((Role.CENTRAL_COMMITTEE,), (None, "always"))]),
    Action.REPORT_CLAIM: _rules([(_OPS, ("report", "report"))]),
    Action.REPORT_STATUS: _rules([(_OPS, ("report", "report"))]),
    Action.REPORT_LINK: _rules([(_OPS, ("report", "report"))]),
    Action.REPORT_REFER: _rules([((*_OPS, Role.CENTRAL_COMMITTEE), (None, "always"))]),
    Action.REPORT_GEO_VERIFY: _rules([((*_OPS, Role.CENTRAL_COMMITTEE), (None, "always"))]),
    Action.REPORT_REFERRAL_DECIDE: _rules([((*_OPS, Role.LOCAL_COMMITTEE), ("target", None))]),
    Action.INCIDENT_CARD: _rules([(_FIELD, ("incident", "always")), ((Role.CENTRAL_COMMITTEE,), (None, "always"))]),
    Action.INCIDENT_NOTE: _rules([(_FIELD, ("incident", "always")), ((Role.CENTRAL_COMMITTEE,), (None, "always"))]),
    Action.INCIDENT_ASSIGN: _rules([(_FIELD, ("incident", "field"))]),
    Action.INCIDENT_CALLOUT: _rules([(_FIELD, ("incident", "field"))]),
    Action.ASSIGNMENT_STATUS: _rules([(_FIELD, ("incident", "field"))]),
    Action.INCIDENT_CLOSE: _rules([((Role.OPS_MANAGER, Role.FIELD_COMMANDER), ("lead", None))]),
    Action.INCIDENT_PARTICIPANTS: _rules(
        [
            ((Role.OPS_MANAGER,), ("lead", "always")),
            ((Role.LOCAL_COMMITTEE,), ("lead", None)),
            ((Role.CENTRAL_COMMITTEE,), (None, "always")),
        ]
    ),
    Action.INCIDENT_MERGE: _rules(
        [((Role.OPS_MANAGER,), ("lead", "always")), ((Role.CENTRAL_COMMITTEE,), (None, "always"))]
    ),
    Action.INCIDENT_LEAD_TRANSFER: _rules([((Role.OPS_MANAGER, Role.CENTRAL_COMMITTEE), (None, "always"))]),
    Action.INCIDENT_COMMAND_LEVEL: _rules([((Role.OPS_MANAGER, Role.CENTRAL_COMMITTEE), (None, "always"))]),
    Action.RESOURCE_REQUEST_CREATE: _rules(
        [(_REQUESTERS, ("incident", "always")), ((Role.CENTRAL_COMMITTEE,), (None, "always"))]
    ),
    Action.RESOURCE_REQUEST_DECIDE: _rules(
        [
            ((Role.OPS_MANAGER, Role.LOCAL_COMMITTEE), ("lead", None)),
            ((Role.CENTRAL_COMMITTEE,), (None, "central_level")),
        ]
    ),
    Action.DIRECTIVE_ISSUE: _rules(
        [
            ((Role.OPS_MANAGER,), (None, "late")),
            ((Role.LOCAL_COMMITTEE,), ("lead", None)),
            ((Role.CENTRAL_COMMITTEE,), (None, "always")),
        ]
    ),
    Action.SETTINGS_WRITE: _rules([((Role.CENTRAL_COMMITTEE, Role.AI_ADMIN, Role.SECURITY_ADMIN), (None, "always"))]),
    Action.BREAKGLASS_REQUEST: _rules(
        [(_REQUESTERS, ("any", "always")), ((Role.CENTRAL_COMMITTEE,), (None, "always"))]
    ),
    Action.BREAKGLASS_REVIEW: _rules([((Role.SECURITY_ADMIN,), (None, "always"))]),
    Action.AUDIT_READ_RAW: _rules([((Role.SECURITY_ADMIN,), (None, "always"))]),
    Action.AUDIT_READ_SCOPED: _rules([((Role.OPS_MANAGER, Role.LOCAL_COMMITTEE, Role.SECURITY_ADMIN), ("any", None))]),
    Action.ACCOUNT_MANAGE: _rules([((Role.REGIONAL_ACCOUNT_ADMIN,), ("lead", "always"))]),
    Action.UNITS_WRITE: _rules([((Role.OPS_MANAGER,), ("lead", "always"))]),
    Action.RESOURCES_WRITE: _rules([((Role.OPS_MANAGER,), ("lead", "always"))]),
}

# Actions without an object: never 404, a regional caller of a national-only action gets national_scope_required.
_OBJECTLESS = frozenset(
    {
        Action.SETTINGS_WRITE,
        Action.BREAKGLASS_REQUEST,
        Action.BREAKGLASS_REVIEW,
        Action.AUDIT_READ_RAW,
        Action.AUDIT_READ_SCOPED,
        Action.DIRECTIVE_ISSUE,
    }
)
# Objects of the caller's own gouvernorat only (no participants, no grants).
_OWN_GOUVERNORAT = frozenset({Action.ACCOUNT_MANAGE, Action.UNITS_WRITE, Action.RESOURCES_WRITE})
_READS = frozenset({Action.REPORT_READ, Action.INCIDENT_READ})
_CLAIMS = frozenset({Action.REPORT_CLAIM, Action.REPORT_STATUS, Action.REPORT_LINK})
# Most specific refusal first when several roles are refused for different reasons.
_REFUSALS = (FIELD_ACTION_REGIONAL_ONLY, NOT_CLAIMABLE, NATIONAL_SCOPE_REQUIRED, ACTION_NOT_ALLOWED)


def _sees(code: int, ctx: Ctx) -> bool:
    return (
        code == ctx.lead
        or code in ctx.participants
        or (ctx.critical and code in ctx.candidates)
        or code == ctx.referred_to
        or ctx.claimed_room == f"g:{code}"
    )


def _regional_ok(rule: Regional, code: int, ctx: Ctx) -> bool:
    match rule:
        case "sees":
            return _sees(code, ctx)
        case "report":
            return code == ctx.lead or (ctx.critical and code in ctx.candidates) or ctx.claimed_room == f"g:{code}"
        case "incident":
            return code == ctx.lead or code in ctx.participants
        case "lead":
            return code == ctx.lead
        case "target":
            return code == ctx.referred_to
        case "any":
            return True
    return False


def _national_ok(rule: National, ctx: Ctx) -> bool:
    match rule:
        case "always":
            return True
        case "report":
            return ctx.late or ctx.lead is None or ctx.command_level == "central"
        case "late":
            return ctx.late
        case "central_level":
            return ctx.command_level == "central"
    return False


def _refusal(action: Action, principal: Principal, rule: Rule) -> str:
    regional, national = rule
    if principal.is_national and national == "field":
        return FIELD_ACTION_REGIONAL_ONLY
    if action in _CLAIMS:
        return NOT_CLAIMABLE
    if not principal.is_national and regional is None and national is not None and action in _OBJECTLESS:
        return NATIONAL_SCOPE_REQUIRED
    return ACTION_NOT_ALLOWED


# ---------------------------------------------------------------- break-glass grants (W2: modules/access/grants.py)


class Grant(Protocol):
    @property
    def id(self) -> uuid.UUID: ...

    @property
    def target_kind(self) -> str: ...

    @property
    def target_id(self) -> uuid.UUID | None: ...

    @property
    def gouvernorat_code(self) -> int | None: ...


async def active_grants(session: AsyncSession, principal: Principal) -> list[Grant]:
    """Unexpired break-glass grants of the caller (``modules.access.grants``), cached for the session (one request)."""
    if not principal.is_staff or principal.is_national:
        # National staff already read everything; a grant only matters to a regional room.
        return []
    cache: dict[str, list[Grant]] = session.info.setdefault("access.grants", {})
    if principal.subject not in cache:
        from app.modules.access import grants

        cache[principal.subject] = list(await grants.active_grants(session, principal.subject))
    return cache[principal.subject]


def grant_covering(grants: list[Grant], ctx: Ctx) -> Grant | None:
    for grant in grants:
        match grant.target_kind:
            case "report" if grant.target_id is not None and grant.target_id == ctx.report_id:
                return grant
            case "incident" if grant.target_id is not None and grant.target_id == ctx.incident_id:
                return grant
            case "gouvernorat" if grant.gouvernorat_code is not None and (
                grant.gouvernorat_code == ctx.lead
                or grant.gouvernorat_code in ctx.participants
                or grant.gouvernorat_code in ctx.candidates
            ):
                return grant
    return None


# ---------------------------------------------------------------- policy


async def authorize(session: AsyncSession, principal: Principal, action: Action, ctx: Ctx) -> Decision:
    """The one policy function (§1.2): ``Decision.allow``, ``Decision.not_found`` or ``Decision.forbidden(code)``."""
    if not principal.is_staff:
        return Decision.forbidden()
    if action is Action.REPORT_READ_SENSITIVE:
        return await _sensitive(session, principal, ctx)
    rules = {role: MATRIX[action][role] for role in principal.roles if role in MATRIX[action]}
    code = principal.gouvernorat_code
    grant: Grant | None = None
    if action not in _OBJECTLESS and code is not None:
        if action in _OWN_GOUVERNORAT:
            visible = code == ctx.lead
        elif action is Action.RESOURCE_REQUEST_DECIDE:
            visible = code == ctx.lead or code in ctx.participants
        else:
            visible = _sees(code, ctx)
            if not visible and rules:
                grant = grant_covering(await active_grants(session, principal), ctx)
        if not visible and grant is None:
            return Decision.not_found
    if not rules:
        return Decision.forbidden()
    refusals: set[str] = set()
    for rule in rules.values():
        regional, national = rule
        if principal.is_national:
            if _national_ok(national, ctx):
                return Decision.allow
        elif code is not None and _regional_ok(regional, code, ctx):
            return Decision.allow
        refusals.add(_refusal(action, principal, rule))
    if grant is not None and action in _READS:
        return Decision.through_grant(grant.id)
    return Decision.forbidden(next(r for r in _REFUSALS if r in refusals))


async def _sensitive(session: AsyncSession, principal: Principal, ctx: Ctx) -> Decision:
    """Reporter identity (§1.3): the handling operations room, or a break-glass grant (audited by the caller)."""
    room = room_of(principal)
    code = principal.gouvernorat_code
    visible = code is None or _sees(code, ctx)
    if visible and Function.OPERATIONS.value in principal.functions:
        if ctx.claimed_room == room:
            return Decision.allow
        if ctx.incident_id is not None and await _handles_incident(session, principal, ctx.incident_id):
            return Decision.allow
    grant = grant_covering(await active_grants(session, principal), ctx)
    if grant is not None:
        return Decision.through_grant(grant.id)
    return Decision.forbidden() if visible else Decision.not_found


async def _handles_incident(session: AsyncSession, principal: Principal, incident_id: uuid.UUID) -> bool:
    """The caller's room leads the incident and works on it (a claimed member report or an active assignment)."""
    code = principal.gouvernorat_code
    found = await session.scalar(
        text(
            "SELECT EXISTS (SELECT 1 FROM ops.incident i WHERE i.id = :incident "
            "AND i.gouvernorat_code IS NOT DISTINCT FROM CAST(:code AS smallint) AND ("
            "EXISTS (SELECT 1 FROM reports.report r WHERE r.incident_id = i.id AND r.claimed_room = :room) "
            "OR (CAST(:code AS smallint) IS NOT NULL AND EXISTS (SELECT 1 FROM ops.assignment a "
            "JOIN ops.resource res ON res.id = a.resource_id JOIN ops.unit u ON u.id = res.unit_id "
            "WHERE a.incident_id = i.id AND a.status IN ('ordered', 'en_route', 'on_scene') "
            "AND u.gouvernorat_code = CAST(:code AS smallint)))))"
        ),
        {"incident": incident_id, "code": code, "room": room_of(principal)},
    )
    return bool(found)


async def visible_gouvernorats(session: AsyncSession, principal: Principal) -> frozenset[int] | None:
    """Gouvernorats whose objects the caller reads wholesale; ``None`` = national (everything)."""
    if principal.is_national:
        return None
    codes = {principal.gouvernorat_code} if principal.gouvernorat_code is not None else set()
    for grant in await active_grants(session, principal):
        if grant.target_kind == "gouvernorat" and grant.gouvernorat_code is not None:
            codes.add(grant.gouvernorat_code)
    return frozenset(codes)


# ---------------------------------------------------------------- database scope (row-level security, §9.1)

# One context variable for the whole process: core.db applies it to every transaction (``ehimaya.*`` settings).
# Set per request by ``security.get_principal`` (staff) and ``identity.get_reporter`` (reporters).
__all__ = ["NO_SCOPE", "SYSTEM_SCOPE", "DbScope", "db_scope"]


def set_db_scope(scope: DbScope) -> Token[DbScope | None]:
    return db_scope.set(scope)


def scope_of_principal(principal: Principal) -> DbScope:
    if principal.is_staff:
        return DbScope.staff(gouvernorat_code=principal.gouvernorat_code, subject=principal.subject)
    # Public-realm caller: no rows until identity.get_reporter knows the account (DbScope.public(user_id)).
    return NO_SCOPE
