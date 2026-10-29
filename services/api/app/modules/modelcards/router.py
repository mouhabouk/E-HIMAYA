"""The "Models" page: the model cards, their PDF, the committee's decisions and the shadow model's training
(docs/phase-l/design-l5.md §4.1 and §4.2). National AI administrator and central committee only."""

import html
from typing import Annotated

import anyio
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service as audit
from app.modules.coastal import service as coastal
from app.modules.coastal import shadow
from app.modules.modelcards import schemas as s
from app.modules.modelcards import service
from app.modules.modelcards.texts import LABELS, Lang

router = APIRouter(prefix="/api/v1/staff/ai/models", tags=["ai"])
Session = Annotated[AsyncSession, Depends(get_session)]
Reader = Annotated[Principal, Depends(require_roles(Role.AI_ADMIN, Role.CENTRAL_COMMITTEE))]
# The committee approves thresholds (AI-01); the AI administrator reads, exports and trains the shadow model.
Committee = Annotated[Principal, Depends(require_roles(Role.CENTRAL_COMMITTEE))]


def _national(principal: Principal) -> None:
    if not principal.is_national:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "national_scope_required")


@router.get("", response_model=s.CardsOut)
async def list_cards(principal: Reader, session: Session, lang: Annotated[Lang, Query()] = "ar") -> s.CardsOut:
    _national(principal)
    return await service.cards(session, principal, lang)


async def _card(session: AsyncSession, principal: Principal, model: str, lang: Lang) -> s.CardOut:
    try:
        return await service.card(session, principal, model, lang)
    except service.UnknownModel:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "model_not_found") from None


@router.post("/{model}/decisions", response_model=s.CardOut, status_code=201)
async def decide(principal: Committee, session: Session, model: str, body: s.DecisionIn) -> s.CardOut:
    """The committee approves the thresholds of the card as shown, or withdraws its approval; audited."""
    _national(principal)
    current = await _card(session, principal, model, "en")
    if not current.can_decide:
        raise HTTPException(status.HTTP_409_CONFLICT, "model_not_trained")
    if body.version != current.version:
        raise HTTPException(status.HTTP_409_CONFLICT, "model_changed")
    row = await service.decide(session, principal, model, body, audit.name_of(principal) or principal.subject)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="ai.model_decision",
        target=f"model:{model}",
        reason=row.reference,
        details={"decision": row.decision, "version": row.version, "thresholds": row.thresholds, "note": row.note},
    )
    await session.commit()
    return await _card(session, principal, model, "ar")


@router.post("/drowning/train", response_model=s.CardOut, status_code=201)
async def train(principal: Reader, session: Session, body: s.TrainIn) -> s.CardOut:
    """Trains a new version of the drowning risk model on [SIM] days; the daily computation uses it in shadow."""
    _national(principal)
    rules = await coastal.rules(session)
    params, metrics = await anyio.to_thread.run_sync(shadow.train, body.seed, rules)
    row = await shadow.store(session, body.seed, params, metrics, audit.name_of(principal) or principal.subject)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="ai.model_trained",
        target=f"model:drowning:{row.version}",
        details={"seed": body.seed, "metrics": metrics},
    )
    await session.commit()
    return await _card(session, principal, "drowning", "ar")


_CSS = """body{font-family:"Noto Naskh Arabic","DejaVu Sans",sans-serif;font-size:10pt;color:#182038}
h1{font-size:17pt;margin:0 0 2pt}h2{font-size:12pt;margin:12pt 0 4pt}p{margin:2pt 0 4pt}
table{border-collapse:collapse;width:100%;margin-top:4pt}
th,td{border:1px solid #E3E7EF;padding:3pt 5pt;text-align:start}
th{background:#F3F5FA}tr.small td{color:#5B6478;font-style:italic}.muted{color:#5B6478;font-size:9pt}
.sim{display:inline-block;background:#F5B400;color:#182038;font-weight:bold;padding:1pt 6pt;border-radius:8pt}
.status{display:inline-block;border:1px solid #182038;padding:1pt 6pt;border-radius:8pt}"""


def _pdf(card: s.CardOut, lang: Lang) -> bytes:
    t = LABELS[lang]
    e = html.escape
    sim = f'<span class="sim">{e(t["sim"])}</span> ' if card.simulated else ""
    parts = [
        f"<h1>{e(t['title'])}: {e(card.name)}</h1>",
        f'<p>{sim}<span class="status">{e(card.status_label)}</span> · {e(t["version"])}: {e(card.version)}</p>',
        f"<h2>{e(t['use'])}</h2><p>{e(card.use)}</p>",
        f"<h2>{e(t['limits'])}</h2><p>{e(card.limits)}</p>",
        f"<h2>{e(t['data'])}</h2><p>{e(card.data)}</p><p class='muted'>{e(' · '.join(card.licences))}</p>",
        f"<h2>{e(t['measures'])}</h2>",
    ]
    for table in card.measures:
        sim_mark = f' <span class="sim">{e(t["sim"])}</span>' if table.simulated else ""
        date_mark = f" · {e(t['measured_on'])} {table.measured_on.isoformat()}" if table.measured_on else ""
        parts.append(f"<p><b>{e(table.title)}</b>{date_mark}{sim_mark}</p>")
        if table.rows:
            head = "".join(f"<th>{e(c)}</th>" for c in table.columns)
            body = "".join(
                f'<tr class="{"small" if i in table.small_rows else ""}">'
                + "".join(f"<td>{e(cell)}</td>" for cell in row)
                + "</tr>"
                for i, row in enumerate(table.rows)
            )
            parts.append(f"<table><tr>{head}</tr>{body}</table>")
        if table.note:
            parts.append(f'<p class="muted">{e(table.note)}</p>')
    parts.append(f"<h2>{e(t['thresholds'])}</h2><table>")
    for th in card.thresholds:
        value = "—" if th.value is None else str(th.value)
        parts.append(f"<tr><td>{e(th.label)}</td><td>{e(value)}</td></tr>")
    parts.append(f"</table><h2>{e(t['decision'])}</h2>")
    if not card.decisions:
        parts.append(f"<p>{e(t['d.none'])}</p>")
    for d in card.decisions:
        parts.append(
            f"<p>{e(t['d.' + d.decision])} · {e(d.decided_by_name)} · {d.decided_at.date().isoformat()} · "
            f"{e(t['d.reference'])}: {e(d.reference)} · {e(d.version)}</p>"
        )
    page = (
        f'<!doctype html><html lang="{lang}" dir="{"rtl" if lang == "ar" else "ltr"}"><head><meta charset="utf-8">'
        f"<style>{_CSS}</style></head><body>{''.join(parts)}</body></html>"
    )
    from weasyprint import HTML

    pdf: bytes = HTML(string=page).write_pdf()
    return pdf


@router.get("/{model}/card.pdf")
async def card_pdf(principal: Reader, session: Session, model: str, lang: Annotated[Lang, Query()] = "ar") -> Response:
    _national(principal)
    card = await _card(session, principal, model, lang)
    pdf = await anyio.to_thread.run_sync(_pdf, card, lang)
    await audit.record(
        session, actor=audit.actor_of(principal), action="ai.model_card_exported", target=f"model:{model}"
    )
    await session.commit()
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="model-card-{model}.pdf"'},
    )
