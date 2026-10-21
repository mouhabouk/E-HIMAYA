"""Prometheus metrics (B2), exposed on ``GET /metrics`` to a scraper holding ``METRICS_TOKEN``.

A dedicated registry keeps the exposition to what operators need. Counters and histograms are per process
(each API or worker container is scraped on its own); queue depths are read from the database at scrape
time, so any instance reports the shared backlog.
"""

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

REGISTRY = CollectorRegistry(auto_describe=True)

REPORT_INGEST_SECONDS = Histogram(
    "ehimaya_report_ingest_seconds",
    "Time to receive and store a new report (POST /api/v1/reports), by reporter kind.",
    ["reporter_kind"],
    buckets=(0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0),
    registry=REGISTRY,
)
OUTBOX_BACKLOG = Gauge(
    "ehimaya_outbox_backlog",
    "Rows waiting in an outbox (events: NATS relay, notify: individual pushes and e-mails).",
    ["outbox"],
    registry=REGISTRY,
)
OUTBOX_OLDEST_AGE_SECONDS = Gauge(
    "ehimaya_outbox_oldest_age_seconds",
    "Age of the oldest row waiting in an outbox; 0 when empty.",
    ["outbox"],
    registry=REGISTRY,
)
AI_QUEUE_DEPTH = Gauge(
    "ehimaya_ai_queue_depth",
    "Reports waiting for (or in) their AI analysis.",
    registry=REGISTRY,
)
NOTIFY_FAILURES = Counter(
    "ehimaya_notify_failures_total",
    "Notification sends that failed, by channel (push, sms, email).",
    ["channel"],
    registry=REGISTRY,
)
RATELIMIT_DEGRADED = Gauge(
    "ehimaya_ratelimit_degraded",
    "1 while Valkey is unreachable and the in-process fallback limiter is used.",
    registry=REGISTRY,
)
SESSION_CHECK_DEGRADED = Counter(
    "ehimaya_session_check_degraded_total",
    "Authenticated requests whose session revocation check was skipped because Valkey was unreachable.",
    registry=REGISTRY,
)
RATELIMIT_BACKEND_ERRORS = Counter(
    "ehimaya_ratelimit_backend_errors_total",
    "Valkey errors seen by the rate limiter.",
    registry=REGISTRY,
)
ANON_BUDGET_EXCEEDED = Counter(
    "ehimaya_anonymous_budget_exceeded_total",
    "Anonymous reports accepted beyond the global anonymous budget (flagged for verification).",
    registry=REGISTRY,
)
REPORTS_FLAGGED = Counter(
    "ehimaya_reports_flagged_total",
    "Reports accepted but flagged for human verification, by reason.",
    ["reason"],
    registry=REGISTRY,
)
MEDIA_QUARANTINED = Counter(
    "ehimaya_media_quarantined_total",
    "Uploaded media quarantined by the verification worker, by reason.",
    ["reason"],
    registry=REGISTRY,
)

_QUEUES_SQL = """
SELECT 'events' AS name, count(*) AS n, coalesce(extract(epoch FROM now() - min(created_at)), 0) AS age
  FROM events.outbox WHERE published_at IS NULL
UNION ALL
SELECT 'notify', count(*), coalesce(extract(epoch FROM now() - min(created_at)), 0)
  FROM notify.outbox WHERE status = 'pending'
UNION ALL
SELECT 'ai', count(*), 0 FROM ai.analysis WHERE state IN ('pending', 'running')
"""


async def refresh_queues(session: AsyncSession) -> None:
    """Read the shared queue depths (called on each scrape)."""
    for name, count, age in (await session.execute(text(_QUEUES_SQL))).all():
        if name == "ai":
            AI_QUEUE_DEPTH.set(count)
        else:
            OUTBOX_BACKLOG.labels(outbox=name).set(count)
            OUTBOX_OLDEST_AGE_SECONDS.labels(outbox=name).set(float(age))
