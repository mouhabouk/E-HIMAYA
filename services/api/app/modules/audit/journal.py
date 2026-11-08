"""The change journal ("mouchard", migration 0097; docs/phase-h/design-h5.md).

Two windows read it:

* ``/api/v1/admin/changes``: the system administrator and the security administrator (national scope) follow every
  addition, update and deletion on the platform's tables, who made it, from which request, and which columns changed.
  Values of personal, secret or free-text columns were never stored (the trigger lists them under ``hidden``); the
  accounts of the public realm (citizens, volunteers, institutions) are shown by a short pseudonym, never by name.
* ``/api/v1/orgs/{org_id}/changes``: the administrator of an institution follows every change to the institution's
  own records (card, members, team, documents, equipment, sites, certificates...), with the names of the members who
  made them; a change made by the civil protection is shown as such, without the staff member's name.

Every read is itself written to the audit log.
"""

import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import Select, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import as_system, get_session
from app.core.security import Principal, Realm, Role, require_roles
from app.modules.audit import service
from app.modules.audit.models import Change

# Tables the journal leaves out (measurements and streams rather than changes, secrets, the audit schema itself).
# Migration 0097 keeps a frozen copy; a migration that creates a table calls audit.journal_attach() for it, or adds
# it here when it is a stream (tests/test_change_journal.py checks that every table is one or the other).
EXCLUDED: frozenset[str] = frozenset(
    {
        "audit.log",
        "audit.change",
        "events.outbox",
        "notify.outbox",
        "notify.dispatch",
        "ops.crew_position",
        "reports.stream_detection",
        "reports.stream_segment",
        "reports.stream_location",
        "reports.drone_telemetry",
        "reports.tracking_counter",
        "reports.camera_event",
        "reports.tower_event",
        "safety.location_point",
        "safety.location_history",
        "sensor.reading",
        "weather.observation",
        "weather.grid_point",
        "coastal.presence",
        "coastal.marine_hour",
        "coastal.beach_day",
        "knowledge.search_doc",
        "knowledge.index_state",
        "decision.procedure_chunk",
        "geo.layer_feature",
        "geo.gouvernorat",
        "geo.delegation",
        "geo.municipality",
        "geo.sector",
        "geo.district",
        "geo.city",
        "geo.economic_region",
        "geo.water_body",
        "identity.email_code",
        "medical.file_key",
        "medical.opinion_key",
        "evidence.leaf",
        "rewards.consumer_cursor",
        "ai.learning_sample",
        "snacr.intervention",
        "snacr.damage",
        "crisis.counter",
        "register.counter",
        "org.certificate_counter",
        "rewards.certificate_counter",
    }
)
# Schemas whose rows are personal as a whole: traced (who, when, which columns), never their values.
PERSONAL_SCHEMAS: frozenset[str] = frozenset(
    {"identity", "medical", "personnel", "safety", "telephony", "contact", "access"}
)

router = APIRouter(tags=["audit"])

JournalReader = Annotated[Principal, Depends(require_roles(Role.SYSADMIN, Role.SECURITY_ADMIN))]
Session = Annotated[AsyncSession, Depends(get_session)]
Op = Literal["I", "U", "D"]
ActorKind = Literal["staff", "public", "system", "database"]


class ChangeOut(BaseModel):
    id: int
    at: datetime
    op: Op
    schema_name: str
    table_name: str
    row_key: dict[str, Any]
    columns: list[str]
    hidden: list[str]
    old_values: dict[str, Any] | None
    new_values: dict[str, Any] | None
    actor_kind: ActorKind
    # Staff: the account and its name; public realm: a short pseudonym; system and database: their label.
    actor: str
    actor_name: str | None
    request_id: str | None
    gouvernorat_code: int | None


class ChangePage(BaseModel):
    items: list[ChangeOut]
    next_cursor: str | None


class Count(BaseModel):
    key: str
    count: int


class ChangeSummary(BaseModel):
    hours: int
    total: int
    by_op: list[Count]
    by_schema: list[Count]
    by_actor_kind: list[Count]
    tables: list[str]


def actor_kind(actor: str) -> ActorKind:
    if actor.startswith(Realm.STAFF.value + ":"):
        return "staff"
    if actor.startswith(Realm.PUBLIC.value + ":"):
        return "public"
    if actor == service.SYSTEM_ACTOR:
        return "system"
    return "database"


def pseudonym(actor: str) -> str:
    """A stable short label for a public-realm account (groups its changes without naming it)."""
    return "public-" + hashlib.sha256(actor.encode()).hexdigest()[:10]


def admin_view(row: Change) -> ChangeOut:
    kind = actor_kind(row.actor)
    return ChangeOut(
        id=row.id,
        at=row.at,
        op=row.op,  # type: ignore[arg-type,unused-ignore]
        schema_name=row.schema_name,
        table_name=row.table_name,
        row_key=row.row_key or {},
        columns=list(row.columns or []),
        hidden=list(row.hidden or []),
        old_values=row.old_values,
        new_values=row.new_values,
        actor_kind=kind,
        actor=pseudonym(row.actor) if kind == "public" else row.actor,
        actor_name=row.actor_name if kind == "staff" else None,
        request_id=row.request_id,
        gouvernorat_code=row.gouvernorat_code,
    )


def _national(principal: Principal) -> None:
    if not principal.is_national:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "national_scope_required")


def _cursor(cursor: str | None) -> int | None:
    if cursor is None:
        return None
    if not cursor.isdigit():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_cursor")
    return int(cursor)


def _filtered(
    query: Select[Change],
    *,
    schema: str | None,
    table: str | None,
    op: Op | None,
    from_: datetime | None,
    to: datetime | None,
    cursor: int | None,
) -> Select[Change]:
    if schema:
        query = query.where(Change.schema_name == schema)
    if table:
        query = query.where(Change.table_name == table)
    if op:
        query = query.where(Change.op == op)
    if from_:
        query = query.where(Change.at >= from_)
    if to:
        query = query.where(Change.at < to)
    if cursor is not None:
        query = query.where(Change.id < cursor)
    return query


Name = Annotated[str | None, Query(max_length=63, pattern=r"^[a-z_][a-z0-9_]*$")]


@router.get("/api/v1/admin/changes", response_model=ChangePage)
async def list_changes(
    principal: JournalReader,
    session: Session,
    schema: Name = None,
    table: Name = None,
    op: Op | None = None,
    actor: Annotated[str | None, Query(max_length=300)] = None,
    actor_kind_: Annotated[ActorKind | None, Query(alias="actor_kind")] = None,
    request_id: Annotated[str | None, Query(max_length=64)] = None,
    row: Annotated[str | None, Query(max_length=100, description="an id of the row (any key column)")] = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ChangePage:
    _national(principal)
    query = _filtered(
        select(Change).order_by(Change.id.desc()).limit(limit),
        schema=schema,
        table=table,
        op=op,
        from_=from_,
        to=to,
        cursor=_cursor(cursor),
    )
    if actor:
        # A staff account by its id; a public-realm one by the pseudonym the list shows.
        if actor.startswith("public-"):
            query = query.where(
                Change.actor.like(Realm.PUBLIC.value + ":%"),
                func.substr(func.encode(func.sha256(func.convert_to(Change.actor, "UTF8")), "hex"), 1, 10)
                == actor.removeprefix("public-"),
            )
        else:
            query = query.where(Change.actor == actor)
    if actor_kind_ == "staff":
        query = query.where(Change.actor.like(Realm.STAFF.value + ":%"))
    elif actor_kind_ == "public":
        query = query.where(Change.actor.like(Realm.PUBLIC.value + ":%"))
    elif actor_kind_ == "system":
        query = query.where(Change.actor == service.SYSTEM_ACTOR)
    elif actor_kind_ == "database":
        query = query.where(Change.actor.like("db:%"))
    if request_id:
        query = query.where(Change.request_id == request_id)
    if row:
        query = query.where(
            text("EXISTS (SELECT 1 FROM jsonb_each_text(audit.change.row_key) AS k WHERE k.value = :row)").bindparams(
                row=row
            )
        )
    rows = list(await session.scalars(query))
    await service.record(
        session,
        actor=service.actor_of(principal),
        action="journal.read",
        details={"schema": schema, "table": table, "op": op, "count": len(rows)},
    )
    await session.commit()
    return ChangePage(items=[admin_view(r) for r in rows], next_cursor=str(rows[-1].id) if len(rows) == limit else None)


async def journaled_tables(session: AsyncSession) -> list[str]:
    rows = await session.execute(
        text(
            "SELECT DISTINCT n.nspname || '.' || c.relname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
            "JOIN pg_namespace n ON n.oid = c.relnamespace WHERE t.tgname = 'zz_journal' ORDER BY 1"
        )
    )
    return [r[0] for r in rows]


@router.get("/api/v1/admin/changes/summary", response_model=ChangeSummary)
async def summary(
    principal: JournalReader, session: Session, hours: Annotated[int, Query(ge=1, le=24 * 31)] = 24
) -> ChangeSummary:
    _national(principal)
    since = datetime.now().astimezone() - timedelta(hours=hours)
    window = Change.at >= since

    async def counts(column: Any) -> list[Count]:
        rows = await session.execute(
            select(column, func.count()).where(window).group_by(column).order_by(func.count().desc()).limit(20)
        )
        return [Count(key=str(k), count=int(c)) for k, c in rows]

    kind = func.split_part(Change.actor, ":", 1)
    by_kind: dict[str, int] = {}
    for c in await counts(kind):
        label = (
            "staff"
            if c.key == Realm.STAFF.value
            else "public"
            if c.key == Realm.PUBLIC.value
            else "system"
            if c.key == service.SYSTEM_ACTOR
            else "database"
        )
        by_kind[label] = by_kind.get(label, 0) + c.count
    by_op = await counts(Change.op)
    return ChangeSummary(
        hours=hours,
        total=sum(c.count for c in by_op),
        by_op=by_op,
        by_schema=await counts(Change.schema_name),
        by_actor_kind=[Count(key=k, count=v) for k, v in sorted(by_kind.items(), key=lambda kv: -kv[1])],
        tables=await journaled_tables(session),
    )


# ---------------------------------------------------------------- an institution's own changes (portal)


class OrgChangeOut(BaseModel):
    id: int
    at: datetime
    op: Op
    table_name: str
    row_key: dict[str, Any]
    columns: list[str]
    hidden: list[str]
    old_values: dict[str, Any] | None
    new_values: dict[str, Any] | None
    # "member": a member of the institution (named); "civil_protection": a staff member; "system": the platform.
    by: Literal["member", "civil_protection", "system"]
    by_name: str | None


class OrgChangePage(BaseModel):
    items: list[OrgChangeOut]
    next_cursor: str | None


def org_view(row: Change, member_names: dict[str, str]) -> OrgChangeOut:
    kind = actor_kind(row.actor)
    by: Literal["member", "civil_protection", "system"] = (
        "civil_protection" if kind == "staff" else "member" if kind == "public" else "system"
    )
    return OrgChangeOut(
        id=row.id,
        at=row.at,
        op=row.op,  # type: ignore[arg-type,unused-ignore]
        table_name=row.table_name,
        row_key=row.row_key or {},
        columns=list(row.columns or []),
        hidden=list(row.hidden or []),
        old_values=row.old_values,
        new_values=row.new_values,
        by=by,
        by_name=member_names.get(row.actor) if by == "member" else None,
    )


async def org_changes(
    session: AsyncSession,
    org_id: uuid.UUID,
    member_names: dict[str, str],
    *,
    table: str | None,
    op: Op | None,
    from_: datetime | None,
    to: datetime | None,
    cursor: str | None,
    limit: int,
) -> OrgChangePage:
    """The changes to one institution's records (the caller checked the admin role); read with the system scope,
    since the journal is national-only for row-level security."""
    query = _filtered(
        select(Change)
        .where(Change.org_id == org_id, Change.schema_name == "org")
        .order_by(Change.id.desc())
        .limit(limit),
        schema=None,
        table=table,
        op=op,
        from_=from_,
        to=to,
        cursor=_cursor(cursor),
    )
    async with as_system(session):
        rows = list(await session.scalars(query))
    return OrgChangePage(
        items=[org_view(r, member_names) for r in rows], next_cursor=str(rows[-1].id) if len(rows) == limit else None
    )
