"""Local and central committees (FR-C-15, FR-C-16): directives with acknowledgements, performance.

The central committee issues directives to the local committees of chosen gouvernorats (or all of
them); a local committee issues directives to its own gouvernorat. Each target gouvernorat
acknowledges once. Performance compares the gouvernorats in the caller's scope.
"""

import base64
import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import and_, any_, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import emit
from app.core.security import Principal, Role
from app.modules.audit import service as audit
from app.modules.ops import schemas
from app.modules.ops.levels import levels_of
from app.modules.ops.models import Directive, DirectiveAck

ALL_GOUVERNORATS_SQL = "SELECT code FROM geo.gouvernorat ORDER BY code"


async def _all_codes(session: AsyncSession) -> list[int]:
    return [int(c) for c in await session.scalars(text(ALL_GOUVERNORATS_SQL))]


def _visible(principal: Principal) -> object:
    if principal.is_national:
        return True
    code = principal.gouvernorat_code
    return or_(
        any_(Directive.gouvernorat_codes) == code,
        Directive.gouvernorat_codes == [],
        Directive.issuer_scope == code,
    )


async def directive_out(session: AsyncSession, directive: Directive, all_codes: list[int]) -> schemas.DirectiveOut:
    acks = list(
        await session.scalars(
            select(DirectiveAck).where(DirectiveAck.directive_id == directive.id).order_by(DirectiveAck.acked_at)
        )
    )
    targets = directive.gouvernorat_codes or all_codes
    acked = {a.gouvernorat_code for a in acks}
    return schemas.DirectiveOut(
        id=directive.id,
        title=directive.title,
        body=directive.body,
        urgency=directive.urgency,
        from_level=directive.from_level,
        issued_by=directive.issued_by_name,
        issued_at=directive.issued_at,
        gouvernorat_codes=list(directive.gouvernorat_codes),
        acks=[
            schemas.DirectiveAckOut(
                gouvernorat_code=a.gouvernorat_code, acked_by=a.acked_by_name, acked_at=a.acked_at, note=a.note
            )
            for a in acks
        ],
        pending_acks=[c for c in targets if c not in acked],
    )


def _encode(at: datetime, directive_id: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(f"{at.isoformat()}|{directive_id}".encode()).decode().rstrip("=")


def _decode(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        at, did = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode().split("|", 1)
        return datetime.fromisoformat(at), uuid.UUID(did)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_cursor") from exc


async def list_directives(
    session: AsyncSession, principal: Principal, pending: bool, limit: int, cursor: str | None
) -> tuple[list[schemas.DirectiveOut], str | None]:
    all_codes = await _all_codes(session)
    query = select(Directive).where(_visible(principal))  # type: ignore[arg-type]
    if pending and principal.gouvernorat_code is not None:
        acked = select(DirectiveAck.directive_id).where(DirectiveAck.gouvernorat_code == principal.gouvernorat_code)
        query = query.where(
            Directive.id.not_in(acked), Directive.issuer_scope.is_distinct_from(principal.gouvernorat_code)
        )
    if cursor:
        at, did = _decode(cursor)
        query = query.where(or_(Directive.issued_at < at, and_(Directive.issued_at == at, Directive.id < did)))
    rows = list(await session.scalars(query.order_by(Directive.issued_at.desc(), Directive.id.desc()).limit(limit)))
    items = [await directive_out(session, d, all_codes) for d in rows]
    if pending and principal.is_national:
        items = [i for i in items if i.pending_acks]
    next_cursor = _encode(rows[-1].issued_at, rows[-1].id) if len(rows) == limit else None
    return items, next_cursor


async def issue(session: AsyncSession, principal: Principal, body: schemas.DirectiveIn) -> schemas.DirectiveOut:
    all_codes = await _all_codes(session)
    codes = sorted(set(body.gouvernorat_codes))
    if any(c not in all_codes for c in codes):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_gouvernorat")
    central = Role.CENTRAL_COMMITTEE in principal.roles and principal.is_national
    if not central:
        # A local committee instructs its own gouvernorat's teams only.
        if principal.gouvernorat_code is None or Role.LOCAL_COMMITTEE not in principal.roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient_role")
        if codes and codes != [principal.gouvernorat_code]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "out_of_scope")
        codes = [principal.gouvernorat_code]
    directive = Directive(
        title=body.title,
        body=body.body,
        urgency=body.urgency,
        from_level="central" if central else "local",
        gouvernorat_codes=codes,
        issuer_scope=principal.gouvernorat_code,
        issued_by=audit.actor_of(principal),
        issued_by_name=audit.name_of(principal),
    )
    session.add(directive)
    await session.flush()
    await session.refresh(directive)
    out = await directive_out(session, directive, all_codes)
    await audit.record(
        session,
        actor=directive.issued_by,
        action="directive.issue",
        target=f"directive:{directive.id}",
        details={"gouvernorat_codes": codes, "urgency": body.urgency},
    )
    await emit(session, "directive.issued", {"directive": out.model_dump(mode="json")})
    return out


async def acknowledge(
    session: AsyncSession, principal: Principal, directive_id: uuid.UUID, note: str | None
) -> schemas.DirectiveOut:
    directive = await session.get(Directive, directive_id)
    code = principal.gouvernorat_code
    targets = directive.gouvernorat_codes if directive is not None else []
    if directive is None or code is None or (targets and code not in targets):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    result = await session.execute(
        insert(DirectiveAck)
        .values(
            directive_id=directive_id,
            gouvernorat_code=code,
            acked_by=audit.actor_of(principal),
            acked_by_name=audit.name_of(principal),
            note=note,
        )
        .on_conflict_do_nothing()
        .returning(DirectiveAck.directive_id)
    )
    if result.first() is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "already_acknowledged")
    await audit.record(
        session, actor=audit.actor_of(principal), action="directive.ack", target=f"directive:{directive_id}"
    )
    out = await directive_out(session, directive, await _all_codes(session))
    await emit(session, "directive.issued", {"directive": out.model_dump(mode="json")})
    return out


_PERFORMANCE = text(
    """
    WITH g AS (
        SELECT code FROM geo.gouvernorat WHERE CAST(:scope AS smallint) IS NULL OR code = CAST(:scope AS smallint)
    ),
    r AS (
        SELECT r.gouvernorat_code AS code, count(*) AS reports,
               count(*) FILTER (WHERE r.status = 'closed') AS closed,
               count(*) FILTER (WHERE r.status = 'rejected') AS rejected,
               avg(extract(epoch FROM r.first_response_at - r.received_at)) AS avg_first,
               avg(extract(epoch FROM c.at - r.received_at)) FILTER (WHERE r.status = 'closed') AS avg_resolution
        FROM reports.report r
        LEFT JOIN LATERAL (
            SELECT max(h.at) AS at FROM reports.status_history h WHERE h.report_id = r.id AND h.status = 'closed'
        ) c ON true
        WHERE r.received_at >= :since
        GROUP BY r.gouvernorat_code
    ),
    i AS (SELECT gouvernorat_code AS code, count(*) AS n FROM ops.incident WHERE status = 'open' GROUP BY 1),
    a AS (
        SELECT i.gouvernorat_code AS code, count(*) AS n FROM ops.assignment a
        JOIN ops.incident i ON i.id = a.incident_id
        WHERE a.status IN ('ordered', 'en_route', 'on_scene') GROUP BY 1
    ),
    v AS (
        SELECT gouvernorat_code AS code, count(*) AS approved,
               count(*) FILTER (WHERE ready_until > now()) AS ready
        FROM identity.volunteer WHERE status = 'approved' GROUP BY 1
    ),
    al AS (
        SELECT g2.code, count(m.id) AS n FROM geo.gouvernorat g2
        JOIN notify.message m ON m.kind = 'alert' AND m.status = 'published' AND m.expires_at > now()
         AND (g2.code = ANY(m.gouvernorat_codes)
              OR (m.area_polygon IS NOT NULL AND ST_Intersects(m.area_polygon, g2.boundary))
              OR (cardinality(m.gouvernorat_codes) = 0 AND m.area_polygon IS NULL))
        GROUP BY g2.code
    )
    SELECT g.code, coalesce(r.reports, 0) AS reports, coalesce(r.closed, 0) AS closed,
           coalesce(r.rejected, 0) AS rejected, r.avg_first, r.avg_resolution,
           coalesce(i.n, 0) AS open_incidents, coalesce(a.n, 0) AS active_assignments,
           coalesce(v.approved, 0) AS volunteers_approved, coalesce(v.ready, 0) AS volunteers_ready,
           coalesce(al.n, 0) AS alerts_active
    FROM g
    LEFT JOIN r ON r.code = g.code
    LEFT JOIN i ON i.code = g.code
    LEFT JOIN a ON a.code = g.code
    LEFT JOIN v ON v.code = g.code
    LEFT JOIN al ON al.code = g.code
    ORDER BY g.code
    """
)


_ACTIVE_ALERTS = text(
    """
    SELECT count(*) FROM notify.message m
    WHERE m.kind = 'alert' AND m.status = 'published' AND m.expires_at > now()
      AND (CAST(:scope AS smallint) IS NULL
           OR CAST(:scope AS smallint) = ANY(m.gouvernorat_codes)
           OR (cardinality(m.gouvernorat_codes) = 0 AND m.area_polygon IS NULL)
           OR ST_Intersects(m.area_polygon,
                            (SELECT boundary FROM geo.gouvernorat WHERE code = CAST(:scope AS smallint))))
    """
)


async def performance(session: AsyncSession, principal: Principal, since: datetime) -> schemas.PerformanceOut:
    rows = (await session.execute(_PERFORMANCE, {"scope": principal.gouvernorat_code, "since": since})).all()
    levels = await levels_of(session)
    out = [
        schemas.PerformanceRow(
            gouvernorat_code=row.code,
            level=levels.get(row.code),
            reports=row.reports,
            closed=row.closed,
            rejected=row.rejected,
            avg_first_response_s=float(row.avg_first) if row.avg_first is not None else None,
            avg_resolution_s=float(row.avg_resolution) if row.avg_resolution is not None else None,
            open_incidents=row.open_incidents,
            active_assignments=row.active_assignments,
            volunteers_approved=row.volunteers_approved,
            volunteers_ready=row.volunteers_ready,
            alerts_active=row.alerts_active,
        )
        for row in rows
    ]

    def weighted(attr: str, weight: str) -> float | None:
        pairs = [(getattr(r, attr), getattr(r, weight)) for r in out if getattr(r, attr) is not None]
        total = sum(w for _, w in pairs)
        return sum(v * w for v, w in pairs) / total if total else None

    national = schemas.PerformanceRow(
        gouvernorat_code=None,
        level=None,
        reports=sum(r.reports for r in out),
        closed=sum(r.closed for r in out),
        rejected=sum(r.rejected for r in out),
        avg_first_response_s=weighted("avg_first_response_s", "reports"),
        avg_resolution_s=weighted("avg_resolution_s", "closed"),
        open_incidents=sum(r.open_incidents for r in out),
        active_assignments=sum(r.active_assignments for r in out),
        volunteers_approved=sum(r.volunteers_approved for r in out),
        volunteers_ready=sum(r.volunteers_ready for r in out),
        alerts_active=int(await session.scalar(_ACTIVE_ALERTS, {"scope": principal.gouvernorat_code}) or 0),
    )
    return schemas.PerformanceOut(since=since, rows=out, national=national)
