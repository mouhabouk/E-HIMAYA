"""The report of a search or of a comparison (L4 §3.4): PDF or XLSX in the reader's language, through the documents of
the reports repository (``analytics.documents``), so the floor of small counts is printed "<5" the same way. The cover
names the criteria, the date of extraction and who extracted it."""

from datetime import UTC, datetime

from app.modules.analytics import domain as analytics_domain
from app.modules.analytics.documents import Column, Content, Section
from app.modules.reports.domain import CATEGORY_LABELS, Category
from app.modules.window import schemas


def _l(ar: str, fr: str, en: str) -> dict[str, str]:
    return {"ar": ar, "fr": fr, "en": en}


METRICS: dict[str, dict[str, str]] = {
    "incidents": _l("التدخلات", "Interventions", "Interventions"),
    "injured": _l("المصابون", "Blessés", "Injured"),
    "deceased": _l("الوفيات", "Décès", "Deaths"),
    "rescued": _l("المنقذون", "Personnes secourues", "Rescued"),
    "burned_ha": _l("المساحة المحروقة (هكتار)", "Surface brûlée (ha)", "Burned area (ha)"),
    "to_assignment_min": _l("زمن التكفل (دقيقة)", "Délai d'engagement (min)", "Time to assignment (min)"),
    "to_on_scene_min": _l("زمن الوصول (دقيقة)", "Délai d'arrivée (min)", "Time to arrival (min)"),
    "reports": _l("البلاغات المستلمة", "Signalements reçus", "Reports received"),
    "confirmed": _l("البلاغات المؤكدة", "Signalements confirmés", "Confirmed reports"),
    "confirmed_rate": _l("نسبة البلاغات المؤكدة", "Taux de confirmation", "Confirmed rate"),
    "category": _l("النوع", "Type", "Type"),
    "severity": _l("الخطورة", "Gravité", "Severity"),
    "status": _l("الحالة", "État", "Status"),
    "gouvernorat": _l("الولاية", "Gouvernorat", "Governorate"),
    "programmes.programmes": _l("البرامج الموسمية", "Programmes saisonniers", "Seasonal programmes"),
    "programmes.posts": _l("نقاط البرامج", "Postes des programmes", "Programme posts"),
    "programmes.lifeguards_planned": _l("السباحون المنقذون المبرمجون", "Maîtres-nageurs prévus", "Lifeguards planned"),
    "programmes.lifeguards_deployed": _l(
        "السباحون المنقذون المنتشرون", "Maîtres-nageurs déployés", "Lifeguards deployed"
    ),
    "programmes.activities_done": _l("أنشطة البرمجة المنجزة", "Activités réalisées", "Activities done"),
    "programmes.rate": _l("نسبة إنجاز البرمجة", "Taux de réalisation", "Completion rate"),
}
STATUS = {"open": _l("جار", "En cours", "Ongoing"), "closed": _l("مغلق", "Clôturé", "Closed")}
FILTERS = {
    "q": _l("البحث", "Recherche", "Search"),
    "category": _l("النوع", "Type", "Type"),
    "classification": _l("النوع الفرعي", "Sous-type", "Sub-type"),
    "severity": _l("الخطورة", "Gravité", "Severity"),
    "status": _l("الحالة", "État", "Status"),
    "source": _l("المصدر", "Source", "Source"),
    "delegation": _l("المعتمدية", "Délégation", "Delegation"),
    "unit": _l("الوحدة", "Unité", "Unit"),
    "org": _l("المؤسسة", "Organisation", "Organisation"),
}
EXTRACTED_BY = _l("استخرجه", "Extrait par", "Extracted by")
DELEGATED = _l("نطاق التفويض", "Périmètre de la délégation", "Delegation scope")
DELEGATED_TEXT = _l("الأحداث المفوَّضة فقط", "Les seuls événements délégués", "The delegated events only")


def key_label(metric: str, key: str, lang: str, names: dict[int, dict[str, str]]) -> str:
    if metric == "category" and key in {c.value for c in Category}:
        return CATEGORY_LABELS[Category(key)][lang]  # type: ignore[index]
    if metric == "status" and key in STATUS:
        return STATUS[key][lang]
    if metric == "gouvernorat" and key.isdigit() and int(key) in names:
        return names[int(key)][lang]
    return key


def _filters(f: schemas.Filters, lang: str, by: str, delegated: bool) -> list[tuple[dict[str, str], str]]:
    out: list[tuple[dict[str, str], str]] = []
    for name, label in FILTERS.items():
        value = getattr(f, name)
        if value in (None, "", []):
            continue
        out.append((label, ", ".join(str(v) for v in value) if isinstance(value, list) else str(value)))
    if delegated:
        out.append((DELEGATED, DELEGATED_TEXT[lang]))
    out.append((EXTRACTED_BY, by))
    return out


def _gouvernorats(codes: list[int], names: dict[int, dict[str, str]], lang: str) -> list[str]:
    return [names[c][lang] if c in names else str(c) for c in codes]


def _breakdown(
    title: dict[str, str],
    metric: str,
    cells: list[schemas.Cell],
    lang: str,
    names: dict[int, dict[str, str]],
    min_cell: int,
) -> Section:
    return Section(
        title,
        [Column(METRICS[metric]), Column(_l("العدد", "Nombre", "Count"), count=True)],
        [[key_label(metric, c.key, lang, names), _shown(metric, c.count, min_cell)] for c in cells],
    )


# Counts: the service answers None for a count under the floor; the report prints it "<5" (other metrics: a dash).
COUNTS = frozenset(
    {
        "incidents",
        "injured",
        "deceased",
        "rescued",
        "reports",
        "confirmed",
        "category",
        "severity",
        "status",
        "gouvernorat",
    }
)


def _shown(metric: str, value: float | None, min_cell: int) -> float | str | None:
    return f"<{min_cell}" if value is None and metric in COUNTS else value


def search_content(
    out: schemas.SearchOut, f: schemas.Filters, lang: str, by: str, names: dict[int, dict[str, str]]
) -> Content:
    fig = out.figures
    scalars = Section(
        _l("المؤشرات", "Indicateurs", "Indicators"),
        [Column(_l("المؤشر", "Indicateur", "Indicator")), Column(_l("القيمة", "Valeur", "Value"))],
        [
            [METRICS[m][lang], _shown(m, getattr(fig, m), out.min_cell)]
            for m in METRICS
            if not m.startswith("programmes") and hasattr(fig, m)
        ],
    )
    items = Section(
        _l("التدخلات", "Interventions", "Interventions"),
        [
            Column(_l("المرجع", "Référence", "Reference")),
            Column(METRICS["category"]),
            Column(METRICS["severity"]),
            Column(METRICS["status"]),
            Column(METRICS["gouvernorat"]),
            Column(_l("الفتح", "Ouverture", "Opened")),
            Column(_l("المحور", "Axe", "Axis")),
        ],
        [
            [
                r.ref,
                key_label("category", r.category, lang, names),
                r.severity,
                key_label("status", r.status, lang, names),
                key_label("gouvernorat", str(r.gouvernorat_code), lang, names) if r.gouvernorat_code else None,
                r.opened_at.astimezone(analytics_domain.TUNIS_TZ).strftime("%Y-%m-%d %H:%M"),
                r.axis_number,
            ]
            for r in out.items
        ],
    )
    return Content(
        title=_l("نافذة القرار: نتيجة بحث", "Fenêtre de décision : résultat de recherche", "Decision window: search")[
            lang
        ],
        kind="window_search",
        lang=lang,
        period=(out.from_.isoformat(), out.to.isoformat()),
        gouvernorats=_gouvernorats(out.gouvernorats, names, lang),
        filters=_filters(f, lang, by, out.delegated),
        min_cell=out.min_cell,
        generated_at=datetime.now(UTC),
        sections=[
            scalars,
            _breakdown(_l("حسب النوع", "Par type", "By type"), "category", fig.by_category, lang, names, out.min_cell),
            _breakdown(
                _l("حسب الخطورة", "Par gravité", "By severity"), "severity", fig.by_severity, lang, names, out.min_cell
            ),
            _breakdown(_l("حسب الحالة", "Par état", "By status"), "status", fig.by_status, lang, names, out.min_cell),
            _breakdown(
                _l("حسب الولاية", "Par gouvernorat", "By governorate"),
                "gouvernorat",
                fig.by_gouvernorat,
                lang,
                names,
                out.min_cell,
            ),
            items,
        ],
    )


def compare_content(
    out: schemas.CompareOut, f: schemas.Filters, lang: str, by: str, names: dict[int, dict[str, str]]
) -> Content:
    def side(s: schemas.Side) -> str:
        where = ", ".join(_gouvernorats(s.gouvernorats, names, lang))
        return f"{s.from_} → {s.to}" + (f" ({where})" if where else "")

    columns = [
        Column(_l("المؤشر", "Indicateur", "Indicator")),
        Column({k: f"A · {side(out.a)}" for k in ("ar", "fr", "en")}),
        Column({k: f"B · {side(out.b)}" for k in ("ar", "fr", "en")}),
        Column(_l("الفارق", "Écart", "Difference")),
        Column(_l("الفارق %", "Écart %", "Difference %")),
    ]
    rows = []
    for r in out.rows:
        name = METRICS.get(r.metric, {}).get(lang, r.metric)
        if r.key is not None:
            name = f"{name}: {key_label(r.metric, r.key, lang, names)}"
        rows.append(
            [
                name,
                _shown(r.metric, r.a, out.min_cell),
                _shown(r.metric, r.b, out.min_cell),
                r.delta,
                f"{round(r.pct * 100, 1)}%" if r.pct is not None else None,
            ]
        )
    start = min(out.a.from_, out.b.from_)
    end = max(out.a.to, out.b.to)
    codes = sorted(set(out.a.gouvernorats) | set(out.b.gouvernorats))
    return Content(
        title=_l("نافذة القرار: مقارنة", "Fenêtre de décision : comparaison", "Decision window: comparison")[lang],
        kind="window_compare",
        lang=lang,
        period=(start.isoformat(), end.isoformat()),
        gouvernorats=_gouvernorats(codes, names, lang),
        filters=_filters(f, lang, by, out.delegated),
        min_cell=out.min_cell,
        generated_at=datetime.now(UTC),
        sections=[Section(_l("المقارنة", "Comparaison", "Comparison"), columns, rows)],
    )
