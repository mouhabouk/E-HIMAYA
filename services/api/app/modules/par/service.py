"""Crew accountability in danger zones, OS7 (docs/phase-os7/design-os7.md).

A team (one assignment of the vehicle a leader holds on shift) enters a danger zone: a timer starts. Every interval
(10 min in a hot zone, 15 in a warm one by default) the leader's phone asks him to confirm that his team is present;
past the grace the commander and the room see a red alarm. Members out for a while (air, water, care, rest) are not
asked for until they are back. A missing resource (radio, breathing apparatus ...) is reported with who had it. The
leader sends his word from the scene: under control or not. The commander or the room may set a time for the next
check, pause the check with a reason and resume it. The check of an incident ends when every team is out, by the
commander or when the incident is closed: everything stays filed with the intervention, off the live follow-up.

The state is computed when it is read: the board and the phone poll it.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import as_system
from app.core.security import Principal
from app.modules.audit import service as audit
from app.modules.ops.models import Assignment, FieldAgent, Incident, Resource, Shift
from app.modules.par import schemas
from app.modules.par.models import Closure, Event, Missing, Setting, Sitrep, Team

DEFAULTS = {"hot_s": 600, "warm_s": 900, "grace_s": 60, "auto_events": ["collapse", "defensive", "evacuation"]}
REMIND_S = 60
MAX_AHEAD = timedelta(hours=12)
RESOURCES = ["جهاز لاسلكي", "جهاز تنفّس", "كاميرا حرارية", "مصباح يدوي"]
AWAY = {
    "air": "تزوّد بالهواء",
    "water_fuel": "تزوّد بالماء أو الوقود",
    "care": "إسعاف",
    "rest": "استراحة",
    "other": "مهمة أخرى",
}
PAUSE = {
    "danger_over": "انتهى الخطر في المنطقة",
    "defensive": "تحوّل إلى الدفاع خارج المبنى",
    "ops_stopped": "توقّف العمليات مؤقتا",
    "comms_failure": "عطل في الاتصال أو التطبيق",
    "other": "سبب آخر",
}
CHECK_ALL = {
    "collapse": "انهيار جزئي أو انفجار",
    "defensive": "التحوّل من الهجوم إلى الدفاع",
    "evacuation": "أمر بالإخلاء",
    "commander": "طلب القائد",
}
SITUATION = {"controlled": "تمت السيطرة", "progress": "في طريق السيطرة", "not_controlled": "لم تتم السيطرة"}
ZONE = {"hot": "المنطقة الساخنة", "warm": "المنطقة الدافئة"}


def now() -> datetime:
    return datetime.now(UTC)


def _name(principal: Principal) -> str | None:
    return audit.name_of(principal)


def _hm(at: datetime) -> str:
    # Shown in Tunisia's time (UTC+1, no summer time since 2009).
    return (at + timedelta(hours=1)).strftime("%H:%M")


def _mmss(seconds: float) -> str:
    s = int(abs(seconds))
    return f"{s // 60:02d}:{s % 60:02d}"


# ---------------------------------------------------------------- settings


async def setting(session: AsyncSession, gouvernorat_code: int | None) -> schemas.SettingOut:
    row = await session.get(Setting, gouvernorat_code) if gouvernorat_code is not None else None
    if row is None:
        return schemas.SettingOut(gouvernorat_code=gouvernorat_code, remind_s=REMIND_S, **DEFAULTS)
    return schemas.SettingOut(
        gouvernorat_code=row.gouvernorat_code,
        hot_s=row.hot_s,
        warm_s=row.warm_s,
        grace_s=row.grace_s,
        auto_events=list(row.auto_events),
        remind_s=REMIND_S,
        updated_at=row.updated_at,
        updated_by_name=row.updated_by_name,
    )


async def save_setting(
    session: AsyncSession, principal: Principal, gouvernorat_code: int, body: schemas.SettingIn
) -> schemas.SettingOut:
    row = await session.get(Setting, gouvernorat_code)
    if row is None:
        row = Setting(gouvernorat_code=gouvernorat_code)
        session.add(row)
    row.hot_s, row.warm_s, row.grace_s = body.hot_s, body.warm_s, body.grace_s
    row.auto_events = sorted(set(body.auto_events))
    row.updated_at, row.updated_by_name = now(), _name(principal)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="par.settings",
        target=f"gouvernorat:{gouvernorat_code}",
        details=body.model_dump(),
        gouvernorats=[gouvernorat_code],
    )
    await session.flush()
    return await setting(session, gouvernorat_code)


# ---------------------------------------------------------------- the state of a team


def interval(team: Team, s: schemas.SettingOut) -> int:
    return s.hot_s if team.zone == "hot" else s.warm_s


def due_at(team: Team, s: schemas.SettingOut) -> datetime:
    return team.next_at or team.last_confirmed_at + timedelta(seconds=interval(team, s))


def remaining(team: Team, s: schemas.SettingOut, at: datetime) -> float:
    """Seconds to the next check (negative: late). Frozen while the check is paused."""
    return (due_at(team, s) - (team.paused_at or at)).total_seconds()


def team_status(team: Team, s: schemas.SettingOut, at: datetime, missing_open: bool) -> str:
    if team.out_at is not None:
        return "out"
    if missing_open:
        return "missing"
    if team.paused_at is not None:
        return "paused"
    r = remaining(team, s, at)
    if r > REMIND_S:
        return "ok"
    if r > 0:
        return "soon"
    if r > -s.grace_s:
        return "late"
    return "alarm"


def _away(team: Team) -> dict[str, Any]:
    return dict(team.away or {})


def team_out(team: Team, s: schemas.SettingOut, at: datetime, missing_open: bool) -> schemas.TeamOut:
    away = _away(team)
    members = [
        schemas.MemberOut(
            key=m["key"],
            name=m["name"],
            role=m.get("role"),
            away_why=away[m["key"]]["why"] if m["key"] in away else None,
            away_at=datetime.fromisoformat(away[m["key"]]["at"]) if m["key"] in away else None,
        )
        for m in team.members
    ]
    st = team_status(team, s, at, missing_open)
    live = team.out_at is None
    return schemas.TeamOut(
        id=team.id,
        assignment_id=team.assignment_id,
        incident_id=team.incident_id,
        label=team.label,
        task=team.task,
        zone=team.zone,
        status=st,
        interval_s=interval(team, s),
        due_at=due_at(team, s) if live and team.paused_at is None else None,
        remaining_s=round(remaining(team, s, at)) if live else None,
        last_confirmed_at=team.last_confirmed_at,
        next_at=team.next_at,
        paused_at=team.paused_at,
        pause_reason=team.pause_reason,
        out_at=team.out_at,
        out_count=team.out_count,
        entered_at=team.entered_at,
        leader_name=team.leader_name,
        members=members,
        present=len(members) - len(away),
        away=len(away),
    )


async def log(
    session: AsyncSession, incident: Incident, team: Team | None, kind: str, text: str, by: str | None
) -> None:
    session.add(
        Event(
            incident_id=incident.id,
            team_id=team.id if team else None,
            gouvernorat_code=incident.gouvernorat_code,
            at=now(),
            kind=kind,
            text=text[:600],
            by_name=by,
        )
    )


async def _teams(session: AsyncSession, incident_id: uuid.UUID) -> list[Team]:
    rows = await session.scalars(select(Team).where(Team.incident_id == incident_id).order_by(Team.entered_at))
    return list(rows)


async def _open_missing(session: AsyncSession, incident_id: uuid.UUID) -> list[Missing]:
    rows = await session.scalars(
        select(Missing)
        .where(Missing.incident_id == incident_id, Missing.recovered_at.is_(None))
        .order_by(Missing.reported_at)
    )
    return list(rows)


async def _watch(session: AsyncSession, incident: Incident, teams: list[Team], s: schemas.SettingOut) -> None:
    """Log the alarm of a team past its grace once, and close the check of a closed incident."""
    at = now()
    open_missing = {m.team_id for m in await _open_missing(session, incident.id)}
    for team in teams:
        st = team_status(team, s, at, team.id in open_missing)
        if st == "alarm" and team.alarmed_at is None:
            team.alarmed_at = at
            await log(
                session,
                incident,
                team,
                "alarm",
                f"{team.label} لم يؤكّد الحضور بعد مهلة السماح · إنذار القائد والقاعة",
                None,
            )
    if incident.status in ("closed", "dissolved") and await session.get(Closure, incident.id) is None and teams:
        await _close(session, incident, teams, None, automatic=True)


# ---------------------------------------------------------------- reading


def _missing_out(m: Missing, labels: dict[uuid.UUID, str]) -> schemas.MissingOut:
    return schemas.MissingOut(
        id=m.id,
        team_id=m.team_id,
        team_label=labels.get(m.team_id, ""),
        resource=m.resource,
        carrier=m.carrier,
        place=m.place,
        reported_at=m.reported_at,
        reported_by_name=m.reported_by_name,
        replacement_at=m.replacement_at,
        recovered_at=m.recovered_at,
        recovered_by_name=m.recovered_by_name,
    )


def _sitrep_out(r: Sitrep, labels: dict[uuid.UUID, str]) -> schemas.SitrepOut:
    return schemas.SitrepOut(
        id=r.id,
        team_id=r.team_id,
        team_label=labels.get(r.team_id, ""),
        at=r.at,
        situation=r.situation,
        reinforcement=r.reinforcement,
        text=r.text,
        voice_seconds=r.voice_seconds,
        edited=bool(r.transcript is not None and (r.text or "").strip() != r.transcript.strip()),
        by_name=r.by_name,
    )


def _closure_out(c: Closure | None) -> schemas.ClosureOut | None:
    if c is None:
        return None
    return schemas.ClosureOut(
        closed_at=c.closed_at, closed_by_name=c.closed_by_name, automatic=c.automatic, summary=dict(c.summary)
    )


async def board(session: AsyncSession, incident: Incident) -> schemas.Board:
    s = await setting(session, incident.gouvernorat_code)
    teams = await _teams(session, incident.id)
    await _watch(session, incident, teams, s)
    at = now()
    labels = {t.id: t.label for t in teams}
    missing = list(
        await session.scalars(select(Missing).where(Missing.incident_id == incident.id).order_by(Missing.reported_at))
    )
    open_teams = {m.team_id for m in missing if m.recovered_at is None}
    outs = [team_out(t, s, at, t.id in open_teams) for t in teams]
    sitreps = await session.scalars(
        select(Sitrep).where(Sitrep.incident_id == incident.id).order_by(Sitrep.at.desc()).limit(20)
    )
    events = await session.scalars(
        select(Event).where(Event.incident_id == incident.id).order_by(Event.at.desc(), Event.id.desc()).limit(200)
    )
    inside = [t for t in outs if t.out_at is None]
    return schemas.Board(
        incident_id=incident.id,
        incident_kind=incident.category,
        incident_status=incident.status,
        gouvernorat_code=incident.gouvernorat_code,
        settings=s,
        kpis=schemas.Kpis(
            agents_in=sum(t.present for t in inside),
            teams_in=len(inside),
            not_confirmed=sum(1 for t in inside if t.status == "alarm"),
            missing_open=sum(1 for m in missing if m.recovered_at is None),
        ),
        teams=outs,
        missing=[_missing_out(m, labels) for m in missing],
        sitreps=[_sitrep_out(r, labels) for r in sitreps],
        events=[
            schemas.EventOut(at=e.at, kind=e.kind, text=e.text, by_name=e.by_name, team_id=e.team_id) for e in events
        ],
        all_out=bool(teams) and not inside,
        closure=_closure_out(await session.get(Closure, incident.id)),
        now=at,
    )


async def incidents(session: AsyncSession, include_closed: bool = False) -> list[schemas.IncidentRow]:
    """The incidents with teams in a danger zone (row level security keeps a regional room to its own)."""
    ids = list(await session.scalars(select(Team.incident_id).distinct()))
    rows: list[schemas.IncidentRow] = []
    for incident_id in ids:
        closed = await session.get(Closure, incident_id) is not None
        if closed and not include_closed:
            continue
        async with as_system(session):
            incident = await session.get(Incident, incident_id)
        if incident is None:
            continue
        b = await board(session, incident)
        rows.append(
            schemas.IncidentRow(
                incident_id=incident.id,
                incident_kind=incident.category,
                gouvernorat_code=incident.gouvernorat_code,
                teams_in=b.kpis.teams_in,
                agents_in=b.kpis.agents_in,
                alarms=b.kpis.not_confirmed,
                missing_open=b.kpis.missing_open,
                last_sitrep=b.sitreps[0].situation if b.sitreps else None,
                closed=b.closure is not None,
            )
        )
    return rows


# ---------------------------------------------------------------- the room's actions


def _live(teams: list[Team], team_id: uuid.UUID | None) -> list[Team]:
    chosen = [t for t in teams if t.out_at is None and (team_id is None or t.id == team_id)]
    if team_id is not None and not chosen:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "team_not_inside")
    return chosen


async def not_closed(session: AsyncSession, incident: Incident) -> None:
    if await session.get(Closure, incident.id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "par_closed")


def _who(team_id: uuid.UUID | None, teams: list[Team]) -> str:
    return teams[0].label if team_id is not None and teams else "كل الفرق في المنطقة"


async def set_next(session: AsyncSession, principal: Principal, incident: Incident, body: schemas.NextIn) -> None:
    await not_closed(session, incident)
    at = now()
    target = body.at.astimezone(UTC)
    if target <= at:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "time_passed")
    if target - at > MAX_AHEAD:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "time_too_far")
    teams = _live(await _teams(session, incident.id), body.team_id)
    for t in teams:
        t.next_at, t.alarmed_at = target, None
    await log(
        session,
        incident,
        teams[0] if body.team_id else None,
        "next",
        f"توقيت خاص للتفقّد القادم {_hm(target)} · {_who(body.team_id, teams)}",
        _name(principal),
    )


async def clear_next(session: AsyncSession, principal: Principal, incident: Incident, body: schemas.TeamsIn) -> None:
    teams = [t for t in _live(await _teams(session, incident.id), body.team_id) if t.next_at is not None]
    for t in teams:
        t.next_at = None
    if teams:
        await log(session, incident, None, "next_clear", "أُلغي التوقيت الخاص · تعود المدة العادية", _name(principal))


async def pause(session: AsyncSession, principal: Principal, incident: Incident, body: schemas.PauseIn) -> None:
    await not_closed(session, incident)
    detail = (body.detail or "").strip()
    if body.reason == "other" and len(detail) < 2:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "reason_detail_required")
    reason = PAUSE[body.reason] + (f" · {detail}" if detail else "")
    teams = [t for t in _live(await _teams(session, incident.id), body.team_id) if t.paused_at is None]
    at = now()
    for t in teams:
        t.paused_at, t.pause_reason, t.alarmed_at = at, reason, None
    if teams:
        await log(
            session,
            incident,
            teams[0] if body.team_id else None,
            "pause",
            f"أُوقف التفقّد · {_who(body.team_id, teams)} · السبب: {reason}",
            _name(principal),
        )
        await audit.record(
            session,
            actor=audit.actor_of(principal),
            action="par.pause",
            target=f"incident:{incident.id}",
            reason=reason,
            gouvernorats=[incident.gouvernorat_code] if incident.gouvernorat_code else None,
        )


async def resume(session: AsyncSession, principal: Principal, incident: Incident, body: schemas.TeamsIn) -> None:
    teams = [t for t in _live(await _teams(session, incident.id), body.team_id) if t.paused_at is not None]
    at = now()
    for t in teams:
        # The timer goes on from where it stopped.
        held = at - (t.paused_at or at)
        t.last_confirmed_at += held
        if t.next_at is not None:
            t.next_at += held
        t.paused_at, t.pause_reason = None, None
    if teams:
        names = "، ".join(t.label for t in teams)
        await log(session, incident, None, "resume", f"استُؤنف التفقّد · {names}", _name(principal))


async def check_all(session: AsyncSession, principal: Principal, incident: Incident, body: schemas.CheckAllIn) -> None:
    await not_closed(session, incident)
    at = now()
    for t in _live(await _teams(session, incident.id), None):
        if t.paused_at is None:
            t.next_at, t.alarmed_at = at, None
    text = f"تفقّد عام فوري · السبب: {CHECK_ALL[body.reason]}"
    await log(session, incident, None, "check_all", text, _name(principal))


async def radio(session: AsyncSession, principal: Principal, incident: Incident, team: Team) -> None:
    await log(session, incident, team, "radio", f"نداء لاسلكي من القائد إلى {team.label}", _name(principal))


def _confirm(team: Team, at: datetime) -> None:
    team.last_confirmed_at, team.next_at, team.alarmed_at = at, None, None


async def manual_confirm(session: AsyncSession, principal: Principal, incident: Incident, team: Team) -> None:
    if team.out_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "team_out")
    _confirm(team, now())
    present = len(team.members) - len(_away(team))
    await log(
        session,
        incident,
        team,
        "confirm",
        f"{team.label} أكّد الحضور: {present} من {present} · أكّده القائد على اللاسلكي",
        _name(principal),
    )


async def record_out(session: AsyncSession, principal: Principal, incident: Incident, team: Team) -> None:
    if team.out_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "team_out")
    n = len(team.members)
    team.out_at, team.out_count, team.away = now(), n, {}
    await log(
        session,
        incident,
        team,
        "out",
        f"{team.label} خرج من منطقة الخطر كاملا: {n} من {n} · سجّله القائد باللاسلكي",
        _name(principal),
    )


async def replacement(session: AsyncSession, principal: Principal, incident: Incident, m: Missing) -> None:
    if m.recovered_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "recovered")
    m.replacement_at, m.replacement_by_name = now(), _name(principal)
    await log(session, incident, None, "replacement", f"أُرسل بديل · {m.resource}", _name(principal))


async def recovered(session: AsyncSession, principal: Principal, incident: Incident, m: Missing) -> None:
    if m.recovered_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "recovered")
    m.recovered_at, m.recovered_by_name = now(), _name(principal)
    await log(session, incident, None, "recovered", f"استُرجع المورد · {m.resource} · أُلغي البلاغ", _name(principal))


async def _close(
    session: AsyncSession, incident: Incident, teams: list[Team], principal: Principal | None, automatic: bool
) -> Closure:
    sitreps = await session.scalar(select(func.count()).select_from(Sitrep).where(Sitrep.incident_id == incident.id))
    missing = await session.scalar(select(func.count()).select_from(Missing).where(Missing.incident_id == incident.id))
    summary = {
        "teams": len(teams),
        "agents": sum(len(t.members) for t in teams),
        "sitreps": int(sitreps or 0),
        "missing": int(missing or 0),
    }
    at = now()
    for t in teams:
        if t.out_at is None:
            t.out_at, t.out_count = at, None
    closure = Closure(
        incident_id=incident.id,
        gouvernorat_code=incident.gouvernorat_code,
        closed_at=at,
        closed_by_name=_name(principal) if principal else None,
        automatic=automatic,
        summary=summary,
    )
    session.add(closure)
    text = f"انتهى التفقّد · {summary['teams']} فرق · {summary['agents']} عونا · أُرشف في سجل التدخّل وسُحب من المتابعة" + (
        " · بغلق التدخّل" if automatic else ""
    )
    await log(session, incident, None, "closed", text, _name(principal) if principal else None)
    await session.flush()
    return closure


async def close(session: AsyncSession, principal: Principal, incident: Incident) -> None:
    await not_closed(session, incident)
    teams = await _teams(session, incident.id)
    if not teams:
        raise HTTPException(status.HTTP_409_CONFLICT, "no_team")
    if any(t.out_at is None for t in teams):
        raise HTTPException(status.HTTP_409_CONFLICT, "teams_inside")
    if await _open_missing(session, incident.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "missing_open")
    await _close(session, incident, teams, principal, automatic=False)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="par.close",
        target=f"incident:{incident.id}",
        gouvernorats=[incident.gouvernorat_code] if incident.gouvernorat_code else None,
    )


# ---------------------------------------------------------------- the team leader's phone


async def crew_members(session: AsyncSession, principal: Principal, shift: Shift) -> list[dict[str, str]]:
    """The leader, then the crew of the shift: the agents on it, else the names typed at its start."""
    members = [{"key": "m0", "name": _name(principal) or "رئيس الفريق", "role": "رئيس الفريق"}]
    agents: list[FieldAgent] = []
    if shift.crew_agent_ids:
        async with as_system(session):
            agents = list(await session.scalars(select(FieldAgent).where(FieldAgent.id.in_(shift.crew_agent_ids))))
    if agents:
        members += [{"key": f"m{i}", "name": a.name, "role": a.function} for i, a in enumerate(agents, start=1)]
    elif shift.crew_names:
        names = [n.strip() for n in shift.crew_names.replace("،", ",").split(",") if n.strip()]
        members += [{"key": f"m{i}", "name": n[:200], "role": ""} for i, n in enumerate(names, start=1)]
    while len(members) < min(max(shift.crew_size, 1), 20):
        members.append({"key": f"m{len(members)}", "name": f"العون {len(members) + 1}", "role": ""})
    return members[:20]


async def mission_team(session: AsyncSession, assignment: Assignment) -> Team | None:
    """The team of this mission: inside the zone, else the last one that left."""
    return await session.scalar(
        select(Team)
        .where(Team.assignment_id == assignment.id)
        .order_by(Team.out_at.is_(None).desc(), Team.entered_at.desc())
        .limit(1)
    )


async def mission(session: AsyncSession, incident: Incident, assignment: Assignment) -> schemas.MissionPar:
    s = await setting(session, incident.gouvernorat_code)
    teams = await _teams(session, incident.id)
    await _watch(session, incident, teams, s)
    team = await mission_team(session, assignment)
    at = now()
    missing: list[Missing] = []
    last: Sitrep | None = None
    if team is not None:
        missing = list(
            await session.scalars(select(Missing).where(Missing.team_id == team.id, Missing.recovered_at.is_(None)))
        )
        last = await session.scalar(select(Sitrep).where(Sitrep.team_id == team.id).order_by(Sitrep.at.desc()).limit(1))
    labels = {team.id: team.label} if team else {}
    custom = await session.scalars(select(Missing.resource).where(Missing.incident_id == incident.id).distinct())
    resources = RESOURCES + sorted({r for r in custom if r not in RESOURCES})
    return schemas.MissionPar(
        settings=s,
        team=team_out(team, s, at, bool(missing)) if team else None,
        missing=[_missing_out(m, labels) for m in missing],
        last_sitrep=_sitrep_out(last, labels) if last else None,
        closed=await session.get(Closure, incident.id) is not None,
        resources=resources,
        now=at,
    )


def _inside(team: Team | None) -> Team:
    if team is None or team.out_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "not_inside")
    return team


def _member(team: Team, key: str) -> dict[str, Any]:
    found = next((m for m in team.members if m["key"] == key), None)
    if found is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "unknown_member")
    return found


async def enter(
    session: AsyncSession,
    principal: Principal,
    incident: Incident,
    assignment: Assignment,
    shift: Shift,
    body: schemas.EnterIn,
) -> Team:
    await not_closed(session, incident)
    current = await mission_team(session, assignment)
    if current is not None and current.out_at is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "already_inside")
    resource = await session.get(Resource, assignment.resource_id) if assignment.resource_id else None
    label = resource.label if resource else "الفريق"
    at = now()
    team = Team(
        assignment_id=assignment.id,
        incident_id=incident.id,
        gouvernorat_code=incident.gouvernorat_code,
        label=label[:120],
        task=body.task or assignment.order,
        zone=body.zone,
        members=await crew_members(session, principal, shift),
        away={},
        leader_subject=principal.subject,
        leader_name=_name(principal),
        entered_at=at,
        last_confirmed_at=at,
    )
    session.add(team)
    await session.flush()
    s = await setting(session, incident.gouvernorat_code)
    await log(
        session,
        incident,
        team,
        "enter",
        f"{label} دخل {ZONE[body.zone]} · {len(team.members)} أعوان · بدأ العدّاد ({interval(team, s) // 60} د)",
        _name(principal),
    )
    return team


async def confirm(session: AsyncSession, principal: Principal, incident: Incident, team: Team | None) -> None:
    team = _inside(team)
    if team.paused_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "paused")
    _confirm(team, now())
    away = len(_away(team))
    present = len(team.members) - away
    await log(
        session,
        incident,
        team,
        "confirm",
        f"{team.label} أكّد الحضور: {present} من {present} · بضغطة من رئيس الفريق"
        + (f" · {away} خارج مؤقتا" if away else ""),
        _name(principal),
    )


async def go_away(
    session: AsyncSession, principal: Principal, incident: Incident, team: Team | None, body: schemas.AwayIn
) -> None:
    team = _inside(team)
    m = _member(team, body.member)
    if body.member == "m0":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "leader_stays")
    away = _away(team)
    if body.member in away:
        raise HTTPException(status.HTTP_409_CONFLICT, "already_away")
    away[body.member] = {"why": body.why, "at": now().isoformat()}
    team.away = away
    await log(
        session,
        incident,
        team,
        "away",
        f"خروج مؤقت · {m['name']} ({team.label}) · {AWAY[body.why]} · لا يُحسب في التفقّد حتى يعود",
        _name(principal),
    )


async def come_back(
    session: AsyncSession, principal: Principal, incident: Incident, team: Team | None, body: schemas.MemberIn
) -> None:
    team = _inside(team)
    m = _member(team, body.member)
    away = _away(team)
    if body.member not in away:
        raise HTTPException(status.HTTP_409_CONFLICT, "not_away")
    was = away.pop(body.member)
    team.away = away
    gone = (now() - datetime.fromisoformat(was["at"])).total_seconds()
    await log(
        session,
        incident,
        team,
        "back",
        f"عاد إلى المنطقة · {m['name']} · غاب {_mmss(gone)} ({AWAY[was['why']]})",
        _name(principal),
    )


async def report_missing(
    session: AsyncSession, principal: Principal, incident: Incident, team: Team | None, body: schemas.MissingIn
) -> Missing:
    team = _inside(team)
    m = _member(team, body.member)
    resource = " ".join(body.resource.split())
    row = Missing(
        team_id=team.id,
        incident_id=incident.id,
        gouvernorat_code=incident.gouvernorat_code,
        resource=resource,
        carrier=m["name"],
        place=body.place,
        reported_at=now(),
        reported_by_name=_name(principal),
    )
    session.add(row)
    await log(
        session,
        incident,
        team,
        "missing",
        f"مورد مفقود · {resource} · كان مع {m['name']} ({team.label})"
        + (f" · آخر موقع: {body.place}" if body.place else ""),
        _name(principal),
    )
    await session.flush()
    return row


async def sitrep(
    session: AsyncSession, principal: Principal, incident: Incident, team: Team | None, body: schemas.SitrepIn
) -> Sitrep:
    if team is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "not_inside")
    text = (body.text or "").strip() or None
    row = Sitrep(
        team_id=team.id,
        incident_id=incident.id,
        gouvernorat_code=incident.gouvernorat_code,
        at=now(),
        situation=body.situation,
        reinforcement=body.reinforcement,
        text=text,
        voice_seconds=body.voice_seconds,
        transcript=body.transcript if body.voice_seconds else None,
        by_name=_name(principal),
    )
    session.add(row)
    await log(
        session,
        incident,
        team,
        "sitrep",
        f"ردّ خبر من {team.label} · {SITUATION[body.situation]}"
        + (" · طلب تعزيز" if body.reinforcement else "")
        + (" · رسالة صوتية محوّلة إلى نص" if body.voice_seconds else ""),
        _name(principal),
    )
    await session.flush()
    return row


async def exit_zone(
    session: AsyncSession, principal: Principal, incident: Incident, team: Team | None, body: schemas.ExitIn
) -> None:
    team = _inside(team)
    keys = {m["key"] for m in team.members}
    if set(body.members) != keys:
        # The timer stops only when every member is out; a member short keeps the team under watch.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "headcount_incomplete")
    n = len(keys)
    team.out_at, team.out_count, team.away, team.paused_at, team.pause_reason = now(), n, {}, None, None
    await log(
        session,
        incident,
        team,
        "out",
        f"{team.label} خرج من منطقة الخطر كاملا: {n} من {n} · أوقِف العدّاد",
        _name(principal),
    )
