"""Analytics vocabulary: roles, labels (ar/fr), the k-anonymity floor, report periods and schedule times.

Pure functions only (no database), shared by the API, the document renderers and the worker.
"""

import calendar
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from app.core.security import Role
from app.modules.reports.domain import CATEGORY_LABELS, Category, Status

TUNIS_TZ = ZoneInfo("Africa/Tunis")

# Who reads analytics and the reports library (the readers of reports), who runs scenarios and asks for documents,
# who manages scheduled reports.
READ_ROLES = (Role.OPERATOR, Role.OPS_MANAGER, Role.FIELD_COMMANDER, Role.LOCAL_COMMITTEE, Role.CENTRAL_COMMITTEE)
PLANNER_ROLES = (Role.OPS_MANAGER, Role.FIELD_COMMANDER, Role.LOCAL_COMMITTEE, Role.CENTRAL_COMMITTEE)
SCHEDULE_ROLES = (Role.OPS_MANAGER, Role.LOCAL_COMMITTEE, Role.CENTRAL_COMMITTEE)

ReportKind = Literal["incident_summary", "period_summary", "gouvernorat_summary", "scenario", "after_action"]
REPORT_KINDS: tuple[ReportKind, ...] = (
    "incident_summary",
    "period_summary",
    "gouvernorat_summary",
    "scenario",
    "after_action",
)
SCHEDULABLE_KINDS = ("period_summary", "gouvernorat_summary")
INCIDENT_KINDS = ("incident_summary", "after_action")
ReportFormat = Literal["pdf", "xlsx"]
ReportLang = Literal["ar", "fr"]
CONTENT_TYPES = {
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

# Report statuses grouped for the overview totals: "verified" = an operator took the report past triage.
VERIFIED_STATUSES = (Status.IN_PROGRESS, Status.INTERVENED, Status.ONGOING, Status.CLOSED)
IN_PROGRESS_STATUSES = (Status.IN_PROGRESS, Status.INTERVENED, Status.ONGOING)
SOURCES = ("app", "sms", "call", "portal", "iot")

LabelPair = dict[str, str]

KIND_LABELS: dict[str, LabelPair] = {
    "incident_summary": {"ar": "ملخص تدخل", "fr": "Synthèse d'intervention"},
    "period_summary": {"ar": "ملخص فترة", "fr": "Synthèse de période"},
    "gouvernorat_summary": {"ar": "ملخص حسب الولاية", "fr": "Synthèse par gouvernorat"},
    "scenario": {"ar": "سيناريو افتراضي", "fr": "Scénario de simulation"},
    "after_action": {"ar": "تقييم ما بعد التدخل", "fr": "Retour d'expérience"},
}
STATUS_LABELS: dict[str, LabelPair] = {
    "received": {"ar": "مستلم", "fr": "Reçu"},
    "in_progress": {"ar": "قيد المعالجة", "fr": "En cours"},
    "intervened": {"ar": "تم التدخل", "fr": "Intervention faite"},
    "ongoing": {"ar": "متواصل", "fr": "En continu"},
    "closed": {"ar": "مغلق", "fr": "Clôturé"},
    "rejected": {"ar": "مرفوض", "fr": "Rejeté"},
}
SOURCE_LABELS: dict[str, LabelPair] = {
    "app": {"ar": "التطبيق", "fr": "Application"},
    "sms": {"ar": "رسالة قصيرة", "fr": "SMS"},
    "call": {"ar": "مكالمة", "fr": "Appel"},
    "portal": {"ar": "البوابة", "fr": "Portail"},
    "iot": {"ar": "أجهزة الاستشعار", "fr": "Capteurs"},
}
RESOURCE_LABELS: dict[str, LabelPair] = {
    "fire_engine": {"ar": "شاحنة إطفاء", "fr": "Engin d'incendie"},
    "water_tanker": {"ar": "صهريج ماء", "fr": "Citerne"},
    "ambulance": {"ar": "سيارة إسعاف", "fr": "Ambulance"},
    "rescue_vehicle": {"ar": "سيارة إنقاذ", "fr": "Véhicule de secours"},
    "heavy_equipment": {"ar": "معدات ثقيلة", "fr": "Engin lourd"},
    "drone": {"ar": "طائرة مسيرة", "fr": "Drone"},
    "large_extinguisher": {"ar": "مطفأة كبيرة", "fr": "Grand extincteur"},
    "boat": {"ar": "زورق", "fr": "Embarcation"},
    "command_vehicle": {"ar": "سيارة قيادة", "fr": "Véhicule de commandement"},
    "other": {"ar": "أخرى", "fr": "Autre"},
}
WEEKDAY_LABELS: dict[int, LabelPair] = {
    1: {"ar": "الإثنين", "fr": "Lundi"},
    2: {"ar": "الثلاثاء", "fr": "Mardi"},
    3: {"ar": "الأربعاء", "fr": "Mercredi"},
    4: {"ar": "الخميس", "fr": "Jeudi"},
    5: {"ar": "الجمعة", "fr": "Vendredi"},
    6: {"ar": "السبت", "fr": "Samedi"},
    7: {"ar": "الأحد", "fr": "Dimanche"},
}


def category_label(category: str | None) -> LabelPair:
    if category is None:
        return {"ar": "كل الأصناف", "fr": "Toutes catégories"}
    try:
        labels = CATEGORY_LABELS[Category(category)]
    except ValueError:
        return {"ar": category, "fr": category}
    return {"ar": labels["ar"], "fr": labels["fr"]}


def label(table: dict[str, LabelPair], key: str | None) -> LabelPair:
    if key is None:
        return {"ar": "—", "fr": "—"}
    return table.get(key, {"ar": key, "fr": key})


# ---------------------------------------------------------------- k-anonymity floor


def floor_cell(value: int | None, min_cell: int) -> int | str | None:
    """A count as printed in an export: below the floor (but not zero) it becomes "<N" (golden rule of phase 8)."""
    if value is None or value == 0 or value >= min_cell:
        return value
    return f"<{min_cell}"


def floor_rule(min_cell: int) -> LabelPair:
    return {
        "ar": f"كل خانة يقل عددها عن {min_cell} بلاغات تظهر في شكل ‎<{min_cell}‎ (حماية من التعرف على الأشخاص). "
        "لا يحتوي هذا التقرير إلا على أعداد ومدد ومساحات، دون أسماء أو أرقام هاتف أو مواقع دقيقة.",
        "fr": f"Toute case de moins de {min_cell} signalements est affichée « <{min_cell} » (seuil de "
        "k-anonymat). Ce document ne contient que des effectifs, des durées et des zones : aucun nom, numéro "
        "de téléphone ni position exacte.",
    }


# ---------------------------------------------------------------- periods and schedules


def day_start(day: date) -> datetime:
    """Midnight of a calendar day in Tunisia, as an aware datetime."""
    return datetime.combine(day, time(0), tzinfo=TUNIS_TZ)


def local_today(now: datetime | None = None) -> date:
    return (now or datetime.now(UTC)).astimezone(TUNIS_TZ).date()


def scheduled_period(frequency: str, run_day: date) -> tuple[date, date]:
    """Period a scheduled document covers when it runs on ``run_day``: the previous day, the previous 7 days or the
    previous calendar month."""
    if frequency == "daily":
        previous = run_day - timedelta(days=1)
        return previous, previous
    if frequency == "weekly":
        return run_day - timedelta(days=7), run_day - timedelta(days=1)
    last = run_day.replace(day=1) - timedelta(days=1)
    return last.replace(day=1), last


def _add_month(day: date, wanted: int) -> date:
    year, month = (day.year + 1, 1) if day.month == 12 else (day.year, day.month + 1)
    return date(year, month, min(wanted, calendar.monthrange(year, month)[1]))


def next_run(frequency: str, at: time, weekday: int | None, day: int | None, after: datetime) -> datetime:
    """First run strictly after ``after`` (aware) of a schedule, at local time ``at`` in Africa/Tunis."""
    local = after.astimezone(TUNIS_TZ)
    today = local.date()
    if frequency == "daily":
        candidate = today
    elif frequency == "weekly":
        assert weekday is not None
        candidate = today + timedelta(days=(weekday - today.isoweekday()) % 7)
    else:
        assert day is not None
        candidate = today.replace(day=day)
    when = datetime.combine(candidate, at, tzinfo=TUNIS_TZ)
    while when <= local:
        if frequency == "daily":
            candidate += timedelta(days=1)
        elif frequency == "weekly":
            candidate += timedelta(days=7)
        else:
            assert day is not None
            candidate = _add_month(candidate, day)
        when = datetime.combine(candidate, at, tzinfo=TUNIS_TZ)
    return when.astimezone(UTC)
