"""The commander's assistant (AI5a, docs/phase-ai5/design-ai5.md §3–§5).

A board of numbered proposals per incident, each one kept in ``decision.command_decision`` with a snapshot of the
situation it was made in, and what the commander did with it:

* the rules of decision support (recommendations.py) are turned into proposals; refreshing the board updates the open
  ones, drops those the situation no longer calls for (``expired``) and never proposes again what the commander already
  decided on in the same words;
* the commander types or dictates a text: a question goes to the incident assistant (cited sources), an order is read
  (orders.py) into a proposal built by the same rules — the resources of the kind asked for ranked by travel time, the
  alert form, the escalation, the volunteers, the responders to call, the route, or a note for the timeline;
* adopting, adopting modified (some actions kept, a note) or rejecting with a reason is recorded, audited and written to
  the incident timeline. Adopting executes nothing: the card's buttons open the existing flows, which keep their own
  confirmation and role checks (AI-01).

Each card shows the assistant's memory: how often commanders adopted, modified or rejected the same proposal in other
incidents of the same category (counts only, read across the country). AI5c turns this memory into a learned ranking.
"""

import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_system_sessionmaker
from app.core.security import Principal
from app.modules.audit import service as audit
from app.modules.decision import assistant, context, domain, orders, recommendations
from app.modules.decision import schemas as s
from app.modules.decision.context import Situation
from app.modules.decision.llm import LlmRejected, LlmUnavailable, get_llm
from app.modules.decision.models import CommandDecision
from app.modules.decision.recommendations import Need
from app.modules.ops.models import Incident, TimelineEvent

log = structlog.get_logger()

NOTICE = s.Bilingual(
    ar="اقتراحات آلية مع مبرراتها: الاعتماد يفتح المسار المعتاد ولا يُنفَّذ أي شيء آليا، والقرار للقائد.",
    fr="Propositions automatiques justifiées : adopter ouvre le circuit habituel, rien n'est exécuté automatiquement, "
    "la décision revient au commandant.",
)
DECIDED_SHOWN = 20
VERDICTS = {"adopt": "adopted", "modify": "modified", "reject": "rejected"}
ORDER_KINDS: dict[str, s.CommandKind] = {
    "dispatch": "resources",
    "route": "route",
    "alert": "alert",
    "escalate": "escalation",
    "volunteers": "volunteers",
    "call": "responders",
    "note": "note",
}


def _b(ar: str, fr: str) -> s.Bilingual:
    return s.Bilingual(ar=ar, fr=fr)


def key_of(item: s.Recommendation) -> str:
    """What a proposal is about, stable across refreshes of the board."""
    inputs = item.inputs
    match item.kind:
        case "resources":
            return f"resources:{inputs.get('resource_kind') or 'location'}"
        case "volunteers":
            return f"volunteers:{inputs.get('skill')}"
        case "escalation":
            return f"escalation:{inputs.get('proposed_level')}"
        case "alert":
            return f"alert:{inputs.get('hazard')}"
        case _:
            return item.kind


def features_of(situation: Situation) -> dict[str, Any]:
    """The figures the proposal was made on: what the assistant learns from. No names, numbers or citizens' words."""
    weather, forecast = situation.weather, situation.forecast
    return {
        "category": situation.category,
        "classification": situation.classification,
        "priority": situation.severity,
        "op_level": situation.op_level,
        "gouvernorat_code": situation.incident.gouvernorat_code,
        "reports": situation.report_count,
        "reporters": situation.reporter_count,
        "lives_at_risk": situation.lives_at_risk,
        "people_trapped": situation.people_trapped,
        "injured": situation.injured,
        "deaths": situation.deaths,
        "hazards": sorted(situation.hazards),
        "people_detected": situation.people_detected,
        "sensitive_site": situation.sensitive_site is not None,
        "engaged": situation.engaged,
        "busy_incidents": situation.busy_incidents,
        "fire_danger": weather.fire_danger if weather else None,
        "rain_level": weather.rain_level if weather else None,
        "wind_kmh": weather.wind_kmh if weather else None,
        "forecast_area_ha": forecast.max_area_ha if forecast else None,
        "forecast_level": forecast.level if forecast else None,
        "located": situation.lat is not None,
        "hour": datetime.now(UTC).hour,
    }


async def tracks(keys: set[str], category: str, incident_id: uuid.UUID) -> dict[str, s.Track]:
    """Decisions on the same proposals in other incidents of the same category, across the country (counts only)."""
    if not keys:
        return {}
    async with get_system_sessionmaker()() as system:
        rows = (
            await system.execute(
                text(
                    "SELECT key, status, reason_code FROM decision.command_decision "
                    "WHERE key = ANY(:keys) AND decided_at IS NOT NULL AND incident_id <> :incident "
                    "AND features->>'category' = :category"
                ),
                {"keys": sorted(keys), "incident": incident_id, "category": category},
            )
        ).all()
    counts: dict[str, Counter[str]] = {k: Counter() for k in keys}
    reasons: dict[str, Counter[str]] = {k: Counter() for k in keys}
    for key, state, reason in rows:
        counts[key][state] += 1
        if reason:
            reasons[key][reason] += 1
    return {
        k: s.Track(
            decided=sum(counts[k].values()),
            adopted=counts[k]["adopted"],
            modified=counts[k]["modified"],
            rejected=counts[k]["rejected"],
            top_reason=reasons[k].most_common(1)[0][0] if reasons[k] else None,
        )
        for k in keys
    }


def card(row: CommandDecision, track: s.Track | None = None) -> s.CommandCard:
    final = row.final or {}
    return s.CommandCard(
        id=row.id,
        incident_id=row.incident_id,
        origin=row.origin,
        kind=row.kind,
        key=row.key,
        title=s.Bilingual.model_validate(row.title),
        rationale=s.Bilingual.model_validate(row.rationale),
        confidence=row.confidence,
        inputs=row.proposal.get("inputs", {}),
        actions=[s.Action.model_validate(a) for a in row.proposal.get("actions", [])],
        status=row.status,
        command_text=row.command_text,
        model=row.model,
        simulated=row.simulated,
        track=track or s.Track(decided=0, adopted=0, modified=0, rejected=0),
        created_at=row.created_at,
        decided_at=row.decided_at,
        decided_by_name=row.decided_by_name,
        kept_actions=final.get("kept_actions"),
        note=final.get("note"),
        reason_code=row.reason_code,
    )


def _fill(row: CommandDecision, item: s.Recommendation, situation: Situation) -> None:
    row.title = item.title.model_dump()
    row.rationale = item.rationale.model_dump()
    row.confidence = item.confidence
    row.proposal = item.model_dump(mode="json", by_alias=True)
    row.features = features_of(situation)
    row.simulated = situation.simulated
    row.updated_at = datetime.now(UTC)


async def _lock(session: AsyncSession, incident_id: uuid.UUID) -> None:
    """One board refresh at a time per incident (the open proposals are unique per subject)."""
    await session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"command:{incident_id}"})


async def _rows(session: AsyncSession, incident_id: uuid.UUID) -> list[CommandDecision]:
    return list(
        (
            await session.scalars(
                select(CommandDecision)
                .where(CommandDecision.incident_id == incident_id)
                .order_by(CommandDecision.created_at.desc())
            )
        ).all()
    )


async def board(session: AsyncSession, principal: Principal, incident: Incident) -> s.CommandBoard:
    situation = await context.gather(session, incident)
    advice = await recommendations.recommend(session, principal, situation)
    await _lock(session, incident.id)
    rows = await _rows(session, incident.id)
    open_rules = {r.key: r for r in rows if r.origin == "rules" and r.status == "proposed"}
    decided = {(r.key, r.title.get("ar")) for r in rows if r.origin == "rules" and r.decided_at is not None}
    actor = audit.actor_of(principal)
    seen: dict[str, int] = {}
    for item in advice.items:
        key = key_of(item)
        if key in seen:
            continue
        seen[key] = len(seen)
        if (key, item.title.ar) in decided:
            continue
        row = open_rules.get(key)
        if row is None:
            row = CommandDecision(
                id=uuid.uuid4(),
                incident_id=incident.id,
                origin="rules",
                kind=item.kind,
                key=key,
                created_by=actor,
                created_at=datetime.now(UTC),
            )
            session.add(row)
            rows.insert(0, row)
        _fill(row, item, situation)
    for key, row in open_rules.items():
        if key not in seen:
            row.status, row.updated_at = "expired", datetime.now(UTC)
    await session.flush()
    proposals = [r for r in rows if r.status == "proposed"]
    # The commander's own orders first (newest first), then the rules in their usual order.
    proposals.sort(
        key=lambda r: (1, seen.get(r.key, 0), 0.0) if r.origin == "rules" else (0, 0, -r.created_at.timestamp())
    )
    done = [r for r in rows if r.decided_at is not None][:DECIDED_SHOWN]
    known = await tracks({r.key for r in proposals + done}, incident.category, incident.id)
    return s.CommandBoard(
        incident_id=incident.id,
        generated_at=advice.generated_at,
        proposals=[card(r, known.get(r.key)) for r in proposals],
        decided=[card(r, known.get(r.key)) for r in done],
        simulated=situation.simulated,
        notice=NOTICE,
    )


# ---------------------------------------------------------------- orders


def _note_item(why: s.Bilingual) -> s.Recommendation:
    """An order the rules cannot turn into a flow: kept as an instruction for the timeline. The stored proposal's
    ``kind`` is not read back (the card's kind is the row's, ``note``)."""
    return s.Recommendation(
        kind="resources",
        title=_b("تعليمة القائد", "Consigne du commandant"),
        rationale=why,
        inputs={},
        confidence="low",
    )


def _escalation(situation: Situation, level: str | None) -> s.Recommendation:
    current = situation.op_level
    target = level or ("crisis" if current == "normal" else "disaster")
    by_rules = recommendations.escalation_item(situation)
    labels = {"crisis": _b("الأزمة", "crise"), "disaster": _b("الكارثة", "catastrophe")}
    target_label = labels.get(target, _b(target, target))
    who = _b("اللجنة الجهوية", "comité régional") if target == "crisis" else _b("اللجنة المركزية", "comité central")
    triggers = by_rules.inputs.get("triggers", []) if by_rules else []
    found = "، ".join(t["ar"] for t in triggers) or "لا مؤشر آلي يدعمه"
    found_fr = ", ".join(t["fr"] for t in triggers) or "aucun indicateur automatique ne l'appuie"
    return s.Recommendation(
        kind="escalation",
        title=_b(f"رفع المستوى إلى {target_label.ar}", f"Passage au niveau {target_label.fr}"),
        rationale=_b(
            f"بأمر القائد. المستوى الحالي: {current}. المؤشرات: {found}. القرار لـ{who.ar} عبر مسار المستويات.",
            f"Sur ordre du commandant. Niveau actuel : {current}. Indicateurs : {found_fr}. Décision du {who.fr} "
            "par le circuit des niveaux.",
        ),
        inputs={"op_level": current, "proposed_level": target, "triggers": triggers},
        confidence="high" if len(triggers) >= 2 else "medium" if triggers else "low",
    )


async def order_item(
    session: AsyncSession, principal: Principal, situation: Situation, reading: orders.Reading
) -> tuple[s.CommandKind, s.Recommendation]:
    """The proposal an order calls for, built by the same rules as the board."""
    action = reading.action or "note"
    ordered = _b("بأمر القائد", "sur ordre du commandant")
    if action in ("dispatch", "route"):
        if situation.lat is None:
            why = _b(
                "لا يمكن اقتراح وسائل ولا مسلك دون موقع الحادثة: اربطوا بلاغا محدد الموقع.",
                "Impossible sans position de l'incident : rattacher un signalement localisé.",
            )
            return "note", _note_item(why)
        if not reading.resource_kind and action == "dispatch":
            why = _b(
                "لم أتعرّف على نوع الوسيلة في الأمر: عدّلوه بذكر الوسيلة (شاحنة إطفاء، إسعاف، صهريج...).",
                "Type de moyen non reconnu dans l'ordre : le préciser (fourgon, ambulance, citerne...).",
            )
            return "note", _note_item(why)
        kind = reading.resource_kind
        wanted = [Need(kind, reading.count or 1, [ordered])] if kind else None
        items, origin = await recommendations.resource_items(session, principal, situation, ordered=wanted)
        if action == "dispatch":
            return "resources", items[0]
        if origin is None:
            label = domain.RESOURCE_LABELS.get(kind or "other", domain.RESOURCE_LABELS["other"])
            why = _b(f"لا توجد {label['ar']} متاحة لحساب المسلك.", f"Aucun(e) {label['fr']} disponible.")
            return "note", _note_item(why)
        return "route", await recommendations.route_item(situation, *origin)
    if action == "alert":
        item = recommendations.alert_item(situation, ordered=True)
        if item is None:
            why = _b(
                "لا يوجد نموذج تنبيه لهذا النوع من الحوادث أو الولاية غير معروفة: يُحرَّر التنبيه يدويا.",
                "Pas de modèle d'alerte pour ce type d'incident ou gouvernorat inconnue : rédiger l'alerte à la main.",
            )
            return "note", _note_item(why)
        return "alert", item
    if action == "escalate":
        return "escalation", _escalation(situation, reading.level)
    if action == "volunteers":
        found = await recommendations.volunteer_items(session, principal, situation)
        if not found:
            why = _b(
                "لا يوجد متطوعون جاهزون بالمهارة المطلوبة على أقل من 20 كم.",
                "Aucun volontaire prêt avec la compétence voulue à moins de 20 km.",
            )
            return "note", _note_item(why)
        return "volunteers", found[0]
    if action == "call":
        item = await recommendations.responders_item(session, principal, situation)
        if item is None:
            why = _b("لا توجد جهة مقترحة للاتصال بها.", "Aucun intervenant proposé.")
            return "note", _note_item(why)
        return "responders", item
    return "note", _note_item(
        _b("تعليمة تُسجَّل في الخط الزمني للحادثة عند اعتمادها.", "Consigne inscrite à la chronologie à l'adoption.")
    )


async def command_text(
    session: AsyncSession, principal: Principal, incident: Incident, body: s.CommandTextIn
) -> s.CommandTextOut:
    llm = get_llm()
    fallback = False
    try:
        reading = await orders.read(body.text, llm)
    except (LlmUnavailable, LlmRejected) as exc:
        log.warning("command.reading_fallback", error=str(exc))
        reading, fallback = orders.finish(orders.read_rules(body.text)), True
    if reading.intent == "question":
        answer = await assistant.ask(session, principal, incident, s.AssistantIn(question=body.text, lang=body.lang))
        return s.CommandTextOut(reading=s.Reading(**reading.as_dict()), fallback=fallback, answer=answer)
    situation = await context.gather(session, incident)
    kind, item = await order_item(session, principal, situation, reading)
    shared = situation.as_inputs()
    item.inputs = {"incident": shared, "reading": reading.as_dict(), **item.inputs}
    row = CommandDecision(
        id=uuid.uuid4(),
        incident_id=incident.id,
        origin="order",
        kind=kind,
        key=f"order:{reading.action}" + (f":{reading.resource_kind}" if reading.resource_kind else ""),
        command_text=body.text,
        lang=body.lang,
        model=llm.model if llm is not None and not fallback else None,
        created_by=audit.actor_of(principal),
        created_at=datetime.now(UTC),
    )
    _fill(row, item, situation)
    session.add(row)
    await session.flush()
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="command.order",
        target=f"incident:{incident.id}",
        details={"decision_id": str(row.id), "reading": reading.as_dict(), "model": row.model, "fallback": fallback},
    )
    known = await tracks({row.key}, incident.category, incident.id)
    return s.CommandTextOut(
        reading=s.Reading(**reading.as_dict()), fallback=fallback, card=card(row, known.get(row.key))
    )


# ---------------------------------------------------------------- decisions


async def decide(session: AsyncSession, principal: Principal, row: CommandDecision, body: s.DecideIn) -> s.CommandCard:
    if row.status != "proposed":
        raise HTTPException(status.HTTP_409_CONFLICT, "already_decided")
    actions = row.proposal.get("actions", [])
    kept: list[int] | None = None
    if body.verdict == "reject":
        if body.reason_code is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "reason_required")
    elif body.verdict == "modify":
        kept = sorted(set(body.kept_actions or []))
        if any(i >= len(actions) for i in kept):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_action_index")
        if kept == list(range(len(actions))) and not body.note:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "nothing_modified")
    else:
        kept = list(range(len(actions)))
    now = datetime.now(UTC)
    row.status = VERDICTS[body.verdict]
    row.final = {"kept_actions": kept, "note": body.note}
    row.reason_code = body.reason_code if body.verdict == "reject" else None
    row.reason_text = body.note if body.verdict == "reject" else None
    row.decided_by = audit.actor_of(principal)
    row.decided_by_name = audit.name_of(principal)
    row.decided_at = row.updated_at = now
    session.add(
        TimelineEvent(
            incident_id=row.incident_id,
            kind="command_decision",
            actor=row.decided_by_name or row.decided_by,
            payload={
                "decision_id": str(row.id),
                "origin": row.origin,
                "key": row.key,
                "verdict": row.status,
                "title": row.title,
                "command_text": row.command_text,
                "kept_actions": kept,
                "note": body.note,
                "reason_code": row.reason_code,
            },
        )
    )
    await audit.record(
        session,
        actor=row.decided_by,
        action="command.decide",
        target=f"incident:{row.incident_id}",
        details={
            "decision_id": str(row.id),
            "key": row.key,
            "origin": row.origin,
            "verdict": row.status,
            "reason_code": row.reason_code,
            "kept_actions": kept,
        },
    )
    await session.flush()
    known = await tracks({row.key}, str(row.features.get("category")), row.incident_id)
    return card(row, known.get(row.key))
