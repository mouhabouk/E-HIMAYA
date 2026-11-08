"""The system logs window (Yamen, 2026-11-08; docs/phase-h/design-h5.md §1).

Every container writes its log to standard output; Grafana Alloy collects them and sends them to Loki (profile
"logs" of compose.prod.yml, retention 30 days). The API and the worker write one JSON object per line
(core/logging.py), with the request id that ties together the lines of one request, its changes in the change
journal (audit.change.request_id) and the X-Request-ID header the client received.

The system administrator and the security administrator (national scope) read them here: the errors of the last
hours by service, and the lines of one service or of one request. The query is built by the API from a few checked
parameters: no LogQL is ever taken from the client. Logs never hold personal data (core/logging.py); every read is
written to the audit log.
"""

import json
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service as audit

log = structlog.get_logger()
router = APIRouter(prefix="/api/v1/admin/logs", tags=["logs"])

LogReader = Annotated[Principal, Depends(require_roles(Role.SYSADMIN, Role.SECURITY_ADMIN))]
Session = Annotated[AsyncSession, Depends(get_session)]
Level = Literal["debug", "info", "warning", "error", "critical"]
_LEVELS: tuple[Level, ...] = ("debug", "info", "warning", "error", "critical")
_TIMEOUT = httpx.Timeout(10.0)


class LogLine(BaseModel):
    at: datetime
    service: str
    level: str | None
    event: str | None
    request_id: str | None
    # The JSON object of the line for the platform's own services, else the raw text.
    fields: dict[str, Any] | None
    text: str | None


class LogPage(BaseModel):
    items: list[LogLine]
    query: str


class ServiceCount(BaseModel):
    service: str
    errors: int
    warnings: int


class LogSummary(BaseModel):
    hours: int
    services: list[ServiceCount]


def _quote(value: str) -> str:
    """A LogQL string literal."""
    return json.dumps(value, ensure_ascii=False)


def selector(service: str | None, min_level: Level | None) -> str:
    labels = [f"service={_quote(service)}" if service else 'service=~".+"']
    if min_level:
        wanted = _LEVELS[_LEVELS.index(min_level) :]
        labels.append(f"level=~{_quote('|'.join(wanted))}")
    return "{" + ", ".join(labels) + "}"


def build_query(service: str | None, min_level: Level | None, request_id: str | None, contains: str | None) -> str:
    query = selector(service, min_level)
    if request_id:
        query += f" |= {_quote(request_id)}"
    if contains:
        query += f" |= {_quote(contains)}"
    return query


def _loki() -> str:
    url = get_settings().loki_url
    if not url:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "logs_not_configured")
    return url.rstrip("/")


async def _get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
            response = await http.get(_loki() + path, params=params)
    except httpx.HTTPError as exc:
        log.warning("logs.loki_unreachable", error=type(exc).__name__)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "logs_unreachable") from exc
    if response.status_code == 400:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "logs_query_refused")
    if response.status_code >= 300:
        log.warning("logs.loki_error", status=response.status_code)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "logs_unreachable")
    body: dict[str, Any] = response.json()
    return body


def _ns(at: datetime) -> str:
    return str(int(at.timestamp() * 1_000_000_000))


def parse_streams(result: list[dict[str, Any]]) -> list[LogLine]:
    lines: list[LogLine] = []
    for stream in result:
        labels = stream.get("stream") or {}
        for ts, raw in stream.get("values") or []:
            fields: dict[str, Any] | None = None
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    fields = parsed
            except ValueError:
                pass
            lines.append(
                LogLine(
                    at=datetime.fromtimestamp(int(ts) / 1_000_000_000, tz=UTC),
                    service=str(labels.get("service") or "?"),
                    level=(fields or {}).get("level") or labels.get("level"),
                    event=(fields or {}).get("event"),
                    request_id=(fields or {}).get("request_id"),
                    fields=fields,
                    text=None if fields is not None else str(raw)[:4000],
                )
            )
    lines.sort(key=lambda line: line.at, reverse=True)
    return lines


ServiceName = Annotated[str | None, Query(max_length=40, pattern=r"^[a-z0-9][a-z0-9_-]*$")]


@router.get("", response_model=LogPage)
async def read_logs(
    principal: LogReader,
    session: Session,
    service: ServiceName = None,
    level: Level | None = None,
    request_id: Annotated[str | None, Query(pattern=r"^[A-Za-z0-9-]{8,64}$")] = None,
    contains: Annotated[str | None, Query(min_length=2, max_length=100)] = None,
    minutes: Annotated[int, Query(ge=1, le=7 * 24 * 60)] = 60,
    until: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> LogPage:
    if not principal.is_national:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "national_scope_required")
    end = until or datetime.now(UTC)
    query = build_query(service, level, request_id, contains)
    body = await _get(
        "/loki/api/v1/query_range",
        {
            "query": query,
            "start": _ns(end - timedelta(minutes=minutes)),
            "end": _ns(end),
            "limit": limit,
            "direction": "backward",
        },
    )
    items = parse_streams((body.get("data") or {}).get("result") or [])[:limit]
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="logs.read",
        details={"service": service, "level": level, "request_id": request_id, "count": len(items)},
    )
    await session.commit()
    return LogPage(items=items, query=query)


@router.get("/summary", response_model=LogSummary)
async def summary(principal: LogReader, hours: Annotated[int, Query(ge=1, le=7 * 24)] = 24) -> LogSummary:
    """Errors (error, critical) and warnings of each service over the last hours."""
    if not principal.is_national:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "national_scope_required")
    counts: dict[str, ServiceCount] = {}
    for key, levels in (("errors", "error|critical"), ("warnings", "warning")):
        body = await _get(
            "/loki/api/v1/query",
            {"query": f'sum by (service) (count_over_time({{service=~".+", level=~"{levels}"}}[{hours}h]))'},
        )
        for item in (body.get("data") or {}).get("result") or []:
            name = str((item.get("metric") or {}).get("service") or "?")
            entry = counts.setdefault(name, ServiceCount(service=name, errors=0, warnings=0))
            value = int(float((item.get("value") or [0, "0"])[1]))
            setattr(entry, key, value)
    services = await _label_values("service")
    for name in services:
        counts.setdefault(name, ServiceCount(service=name, errors=0, warnings=0))
    ordered = sorted(counts.values(), key=lambda c: (-c.errors, -c.warnings, c.service))
    return LogSummary(hours=hours, services=ordered)


async def _label_values(label: str) -> list[str]:
    body = await _get(f"/loki/api/v1/label/{label}/values", {})
    return sorted(str(v) for v in body.get("data") or [])
