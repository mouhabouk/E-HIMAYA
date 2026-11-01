"""The mission sheet (أمر مهمة): the official paper a team takes to the scene (Yamen, 2026-11-01).

One page or two, in Arabic, printed from the room or opened on the leader's phone. It gives everything that helps the
intervention:

* the order, its number and its time, the room that issued it;
* the incident: nature, classification, level, the time of the first report, the reporter (kind, role and, for the
  room that handles the incident, name and phone), what the reports say, the lives at risk;
* the place: gouvernorat, délégation, sector, municipality, coordinates, and a map drawn from the délégation's
  boundary with the route from the unit to the scene in a bold colour (the routing engine's road, else the straight
  line, said so);
* the institution's card when a report comes from one: hazardous materials, evacuation points, representative;
* the vehicle, its unit, the leader and the crew's names, the contact number on the scene;
* the safety notes, then the signatures: the team leader and the duty officer of the room.

The page is built here as HTML and printed by WeasyPrint, as the other documents; the map is SVG, so nothing is
fetched from outside (no tile server is needed to print).
"""

import html
import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import print_footer
from app.core.access import Action, authorize
from app.core.security import Principal
from app.modules.ai.models import Analysis
from app.modules.decision import routing
from app.modules.geo import service as geo_service
from app.modules.geo.models import Gouvernorat
from app.modules.identity.models import Profile
from app.modules.ops.models import Assignment, Incident, Resource, Shift, Unit
from app.modules.orgs import service as orgs
from app.modules.orgs.models import Organization
from app.modules.reports import service as reports
from app.modules.reports.models import Report

TUNIS = ZoneInfo("Africa/Tunis")

CATEGORY = {
    "sos": "نجدة",
    "fire": "حريق",
    "flood": "فيضان",
    "traffic_accident": "حادث مرور",
    "drowning": "غرق",
    "landslide": "انزلاق أرضي",
    "chemical_leak": "تسرب مواد خطرة",
    "medical": "إسعاف",
    "other": "أخرى",
}
CLASSIFICATION = {
    "forest_fire": "حريق غابات",
    "residential_fire": "حريق مسكن",
    "industrial_fire": "حريق صناعي",
    "vehicle_fire": "حريق عربة",
    "river_flood": "فيضان وادٍ",
    "urban_flood": "فيضان حضري",
    "flash_flood": "سيل جارف",
    "road_accident": "حادث طريق",
    "chemical_road_accident": "حادث نقل مواد خطرة",
    "rail_accident": "حادث سكة",
    "beach": "شاطئ",
    "dam_or_lake": "سد أو بحيرة",
    "well": "بئر",
    "landslide": "انزلاق",
    "rockfall": "سقوط صخور",
    "building_collapse": "انهيار بناية",
    "industrial_leak": "تسرب صناعي",
    "transport_leak": "تسرب أثناء النقل",
    "gas_leak": "تسرب غاز",
    "cardiac": "قلبي",
    "trauma": "إصابة",
    "mass_casualty": "إصابات جماعية",
}
LEVEL = {"normal": "عادي", "crisis": "أزمة", "disaster": "كارثة"}
KIND = {"citizen": "مواطن", "organization": "مؤسسة", "anonymous": "مجهول الهوية"}
ROLE = {"volunteer": "متطوّع معتمد", "doctor": "طبيب معتمد"}
RESOURCE = {
    "fire_engine": "شاحنة إطفاء",
    "water_tanker": "صهريج ماء",
    "ambulance": "سيارة إسعاف",
    "rescue": "عربة إنقاذ",
    "heavy_equipment": "آلية ثقيلة",
    "drone": "طائرة مسيّرة",
    "command_vehicle": "عربة قيادة",
    "boat": "زورق",
}
FEATURE = {
    "evacuation_point": "نقطة تجمع وإخلاء",
    "hydrant": "مأخذ ماء",
    "shutoff": "صمام قطع",
    "entrance": "مدخل",
}
ROUTE_COLOR = "#d32f2f"


@dataclass
class Sheet:
    number: str
    issued_at: datetime
    printed_at: datetime
    order: str | None
    contact_phone: str | None
    category: str
    classification: str | None
    level: str
    title: str | None
    gouvernorat: str | None
    delegation: str | None
    sector: str | None
    municipality: str | None
    lat: float | None
    lon: float | None
    first_report_at: datetime | None
    reporter_kind: str
    reporter_roles: list[str]
    reporter_name: str | None
    reporter_phone: str | None
    reporter_masked: bool
    report_count: int
    texts: list[str]
    lives_at_risk: bool
    unit: str | None
    unit_phone: str | None
    vehicle: str | None
    vehicle_kind: str | None
    leader: str | None
    crew_names: str | None
    crew_size: int | None
    route: routing.Route | None
    boundary: dict[str, Any] | None
    org: dict[str, Any] | None
    sensitive: list[str] = field(default_factory=list)


def _local(at: datetime | None) -> str:
    return at.astimezone(TUNIS).strftime("%Y-%m-%d %H:%M") if at else "—"


async def gather(session: AsyncSession, principal: Principal, assignment: Assignment, now: datetime) -> Sheet:
    lat_c = func.ST_Y(cast(Incident.centroid, Geometry))
    lon_c = func.ST_X(cast(Incident.centroid, Geometry))
    incident, lat, lon = (
        await session.execute(select(Incident, lat_c, lon_c).where(Incident.id == assignment.incident_id))
    ).one()
    resource = await session.get(Resource, assignment.resource_id) if assignment.resource_id else None
    unit = await session.get(Unit, resource.unit_id) if resource else None
    shift = await session.get(Shift, assignment.shift_id) if assignment.shift_id else None
    if shift is None and resource is not None:
        # Ordered before the leader acted on it: the shift holding the vehicle now.
        shift = await session.scalar(
            select(Shift).where(Shift.resource_id == resource.id, Shift.ended_at.is_(None)).limit(1)
        )
    members = list(
        await session.scalars(
            select(Report).where(Report.incident_id == incident.id).order_by(Report.received_at, Report.id)
        )
    )
    first = members[0] if members else None
    gouvernorat = await session.get(Gouvernorat, incident.gouvernorat_code) if incident.gouvernorat_code else None
    # The incident's own délégation; the sector and municipality of its first report (where it was sent from).
    address = await geo_service.address_out(
        session,
        incident.delegation_id or (first.delegation_id if first else None),
        first.sector_code if first else None,
        first.municipality_id if first else None,
    )

    reporter_kind, name, phone, masked = "anonymous", None, None, True
    roles: list[str] = []
    org: dict[str, Any] | None = None
    if first is not None:
        summary = await reports.staff_summary(session, first.id)
        if summary is not None:
            reporter_kind = summary[0].reporter_kind
        if reporter_kind != "anonymous":
            roles = [str(r) for r in await reports.reporter_roles(session, first.user_id)]
            ctx = await reports.report_ctx(session, first)
            if (await authorize(session, principal, Action.REPORT_READ_SENSITIVE, ctx)).allowed:
                profile = await session.get(Profile, first.user_id)
                if profile is not None:
                    name = " ".join(x for x in (profile.first_name, profile.last_name) if x) or None
                    phone = profile.phone
                masked = False
    org_report = next((m for m in members if m.organization_id), None)
    if org_report is not None and org_report.organization_id is not None:
        found = await session.get(Organization, org_report.organization_id)
        if found is not None:
            org = (await orgs.organization_card(session, found)).model_dump(mode="json")

    analyses = list(await session.scalars(select(Analysis).where(Analysis.report_id.in_([m.id for m in members]))))
    lives = any(reports._lives_at_risk(a) for a in analyses)

    route = None
    if unit is not None and lat is not None and lon is not None:
        u_lat, u_lon = (
            await session.execute(
                select(func.ST_Y(cast(Unit.location, Geometry)), func.ST_X(cast(Unit.location, Geometry))).where(
                    Unit.id == unit.id
                )
            )
        ).one()
        route = await routing.route(routing.Point(u_lat, u_lon), routing.Point(lat, lon), "truck")
    boundary = None
    delegation_id = incident.delegation_id or (first.delegation_id if first else None)
    if delegation_id is not None:
        raw = await session.scalar(
            text(
                "SELECT ST_AsGeoJSON(ST_SimplifyPreserveTopology(boundary, 0.0005), 5) "
                "FROM geo.delegation WHERE id = :i"
            ),
            {"i": delegation_id},
        )
        boundary = json.loads(raw) if raw else None

    sensitive = []
    if lives:
        sensitive.append("أرواح في خطر حسب البلاغات")
    if org and org.get("hazmat"):
        sensitive.append("مواد خطرة في الموقع: " + "، ".join(h["name"] for h in org["hazmat"]))
    if incident.op_level != "normal":
        sensitive.append(f"المستوى العملياتي: {LEVEL.get(incident.op_level, incident.op_level)}")
    if len(members) > 1:
        sensitive.append(f"{len(members)} بلاغات على الحادث نفسه")

    return Sheet(
        number=f"{now.astimezone(TUNIS):%Y%m%d}-{str(assignment.id)[:8].upper()}",
        issued_at=assignment.created_at,
        printed_at=now,
        order=assignment.order,
        contact_phone=assignment.contact_phone,
        category=incident.category,
        classification=incident.classification,
        level=incident.op_level,
        title=incident.title,
        gouvernorat=gouvernorat.name_ar if gouvernorat else None,
        delegation=address.delegation.name_ar if address and address.delegation else None,
        sector=address.sector.name_ar if address and address.sector else None,
        municipality=address.municipality.name_ar if address and address.municipality else None,
        lat=float(lat) if lat is not None else None,
        lon=float(lon) if lon is not None else None,
        first_report_at=first.received_at if first else None,
        reporter_kind=reporter_kind,
        reporter_roles=roles,
        reporter_name=name,
        reporter_phone=phone,
        reporter_masked=masked,
        report_count=len(members),
        texts=[(m.text_ar or m.text_original or "").strip() for m in members if (m.text_ar or m.text_original)][:5],
        lives_at_risk=lives,
        unit=unit.name_ar if unit else None,
        unit_phone=unit.phone if unit else None,
        vehicle=resource.label if resource else None,
        vehicle_kind=resource.kind if resource else None,
        leader=shift.leader_name if shift else None,
        crew_names=shift.crew_names if shift else None,
        crew_size=shift.crew_size if shift else None,
        route=route,
        boundary=boundary,
        org=org,
        sensitive=sensitive,
    )


# ---------------------------------------------------------------- the map


def _rings(geometry: dict[str, Any] | None) -> list[list[list[float]]]:
    if not geometry:
        return []
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"][0]]
    if geometry["type"] == "MultiPolygon":
        return [poly[0] for poly in geometry["coordinates"]]
    return []


def map_svg(sheet: Sheet, width: int = 680, height: int = 330) -> str:
    """The délégation's outline, the route from the unit (blue) to the scene (red) in a bold colour, the evacuation
    points (green), a north arrow and a scale bar. Equirectangular, scaled by the cosine of the latitude."""
    points: list[list[float]] = []
    route = sheet.route.coordinates if sheet.route else []
    points += route
    rings = _rings(sheet.boundary)
    for ring in rings:
        points += ring
    features = [f for f in (sheet.org or {}).get("features", []) if f.get("location")]
    points += [[f["location"]["lon"], f["location"]["lat"]] for f in features]
    if sheet.lat is not None and sheet.lon is not None:
        points.append([sheet.lon, sheet.lat])
    if not points:
        return ""
    lons = [p[0] for p in points]
    lats = [p[1] for p in points]
    mid = math.cos(math.radians((min(lats) + max(lats)) / 2))
    span_x = max((max(lons) - min(lons)) * mid, 0.004)
    span_y = max(max(lats) - min(lats), 0.004)
    pad = 24
    scale = min((width - 2 * pad) / span_x, (height - 2 * pad) / span_y)
    cx, cy = (min(lons) + max(lons)) / 2, (min(lats) + max(lats)) / 2

    def xy(lon: float, lat: float) -> tuple[float, float]:
        return width / 2 + (lon - cx) * mid * scale, height / 2 - (lat - cy) * scale

    def path(coords: list[list[float]]) -> str:
        return " ".join(f"{x:.1f},{y:.1f}" for x, y in (xy(c[0], c[1]) for c in coords))

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="#f7f9fb" stroke="#90a4ae"/>',
    ]
    for ring in rings:
        out.append(f'<polygon points="{path(ring)}" fill="#e8f0e3" stroke="#7a8f6a" stroke-width="1.2"/>')
    if len(route) >= 2:
        out.append(
            f'<polyline points="{path(route)}" fill="none" stroke="#ffffff" stroke-width="10" '
            'stroke-linejoin="round" stroke-linecap="round"/>'
        )
        dash = ' stroke-dasharray="14 8"' if sheet.route and sheet.route.engine == "fallback" else ""
        out.append(
            f'<polyline points="{path(route)}" fill="none" stroke="{ROUTE_COLOR}" stroke-width="6" '
            f'stroke-linejoin="round" stroke-linecap="round"{dash}/>'
        )
        sx, sy = xy(*route[0])
        out.append(f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="8" fill="#1565c0" stroke="#fff" stroke-width="2"/>')
    for f in features:
        fx, fy = xy(f["location"]["lon"], f["location"]["lat"])
        out.append(f'<rect x="{fx - 6:.1f}" y="{fy - 6:.1f}" width="12" height="12" fill="#2e7d32" stroke="#fff"/>')
    if sheet.lat is not None and sheet.lon is not None:
        ix, iy = xy(sheet.lon, sheet.lat)
        out.append(
            f'<path d="M{ix:.1f},{iy:.1f} l-9,-20 a10,10 0 1,1 18,0 z" fill="{ROUTE_COLOR}" stroke="#fff" '
            'stroke-width="2"/>'
        )
        out.append(f'<circle cx="{ix:.1f}" cy="{iy - 22:.1f}" r="3.5" fill="#fff"/>')
    # North arrow and a scale bar (a round length near a fifth of the width).
    out.append(
        f'<g transform="translate({width - 30},40)"><path d="M0,-18 L8,8 L0,3 L-8,8 Z" fill="#37474f"/>'
        '<text x="0" y="22" font-size="12" text-anchor="middle" fill="#37474f">N</text></g>'
    )
    metres_per_px = 111_320 / scale
    target = metres_per_px * width / 5
    nice = next((v for v in (100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000) if v >= target), 50000)
    bar = nice / metres_per_px
    label = f"{nice // 1000} km" if nice >= 1000 else f"{nice} m"
    out.append(
        f'<g transform="translate(16,{height - 16})"><rect width="{bar:.1f}" height="5" fill="#37474f"/>'
        f'<text x="0" y="-5" font-size="11" fill="#37474f">{label}</text></g>'
    )
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------- the page

_CSS = """
@page { size: A4; margin: 10mm 12mm 32mm 12mm;
  @bottom-center { content: element(footer); width: 100%; } }
body { font-family: "Noto Naskh Arabic", "Noto Sans Arabic", "DejaVu Sans", sans-serif; font-size: 9.5pt;
  color: #1b1b1b; direction: rtl; text-align: right; }
.head { display: flex; justify-content: space-between; border-bottom: 3px solid #b71c1c; padding-bottom: 4px; }
.head .state { font-size: 9pt; line-height: 1.4; }
.head .num { font-size: 9pt; text-align: left; direction: ltr; }
h1 { font-size: 16pt; color: #b71c1c; text-align: center; margin: 6px 0 2px; }
.sub { text-align: center; font-size: 9pt; color: #555; margin-bottom: 6px; }
h2 { font-size: 10.5pt; margin: 6px 0 3px; color: #b71c1c; border-bottom: 1px solid #b71c1c; }
table { width: 100%; border-collapse: collapse; }
th, td { border: 1px solid #c9c9c9; padding: 3px 5px; vertical-align: top; }
th { background: #f4f4f4; width: 24%; font-weight: bold; }
.ltr { direction: ltr; unicode-bidi: isolate; }
.alert { border: 2px solid #b71c1c; background: #fdecea; padding: 5px 8px; margin: 6px 0; font-weight: bold; }
.order { border: 2px solid #1b1b1b; padding: 6px 8px; font-size: 11pt; font-weight: bold; margin: 4px 0; }
.map { text-align: center; margin: 4px 0; }
.legend { font-size: 8pt; color: #444; text-align: center; }
.legend .r { color: #d32f2f; font-weight: bold; } .legend .b { color: #1565c0; } .legend .g { color: #2e7d32; }
.sign { display: flex; gap: 10mm; margin-top: 5mm; page-break-inside: avoid; }
.sign div { flex: 1; border: 1px solid #999; height: 24mm; padding: 4px 6px; }
.sign b { display: block; margin-bottom: 3px; }
.small { font-size: 8pt; color: #555; }
"""


def render_html(sheet: Sheet) -> str:
    e = html.escape

    def row(label: str, value: Any, ltr: bool = False) -> str:
        shown = e(str(value)) if value not in (None, "", []) else "—"
        cls = ' class="ltr"' if ltr and value else ""
        return f"<tr><th>{e(label)}</th><td{cls}>{shown}</td></tr>"

    nature = CATEGORY.get(sheet.category, sheet.category)
    if sheet.classification:
        nature += f" — {CLASSIFICATION.get(sheet.classification, sheet.classification)}"
    reporter = KIND.get(sheet.reporter_kind, sheet.reporter_kind)
    if sheet.reporter_roles:
        reporter += " (" + "، ".join(ROLE.get(r, r) for r in sheet.reporter_roles) + ")"
    if sheet.org:
        reporter += f": {sheet.org['name']}"
    who = (
        "تُحجب هوية المبلّغ خارج القاعة التي تعالج الحادث"
        if sheet.reporter_masked
        else " · ".join(x for x in (sheet.reporter_name, sheet.reporter_phone) if x) or None
    )
    coords = f"{sheet.lat:.5f}, {sheet.lon:.5f}" if sheet.lat is not None and sheet.lon is not None else None
    route = sheet.route
    if route is None:
        route_text = "—"
    else:
        how = "طريق محسوب بمحرك المسالك" if route.engine != "fallback" else "خط مستقيم تقديري (دون محرك المسالك)"
        route_text = f"{route.distance_m / 1000:.1f} كم، نحو {math.ceil(route.duration_s / 60)} دقيقة — {how}"
    texts = "".join(f"<li>{e(t)}</li>" for t in sheet.texts) or "<li>—</li>"
    alerts = "".join(f"<div class='alert'>⚠ {e(s)}</div>" for s in sheet.sensitive)
    vehicle = " · ".join(x for x in (RESOURCE.get(sheet.vehicle_kind or "", sheet.vehicle_kind), sheet.vehicle) if x)

    org_html = ""
    if sheet.org:
        o = sheet.org
        hazmat = "".join(
            f"<tr><td>{e(h['name'])}</td><td class='ltr'>{e(str(h.get('un_number') or '—'))}</td>"
            f"<td class='ltr'>{e(str(h.get('hazard_class') or '—'))}</td>"
            f"<td class='ltr'>{e(str(h.get('quantity')))} {e(str(h.get('unit') or ''))}</td></tr>"
            for h in o.get("hazmat", [])
        )
        feats = "، ".join(
            f"{FEATURE.get(f['kind'], f['kind'])}{(': ' + f['label']) if f.get('label') else ''}"
            for f in o.get("features", [])
        )
        rep = o.get("representative") or {}
        org_html = (
            "<h2>3. بطاقة المؤسسة</h2><table>"
            + row("المؤسسة", o["name"])
            + row("العنوان", o.get("address"))
            + row("طاقة الاستيعاب", o.get("capacity"))
            + row("الممثل", " · ".join(x for x in (rep.get("full_name"), rep.get("phone")) if x) or None)
            + row("نقاط الإخلاء والتجهيزات", feats)
            + "</table>"
            + (
                "<table style='margin-top:4px'><tr><th>المادة الخطرة</th><th>رقم الأمم المتحدة</th><th>الصنف</th>"
                f"<th>الكمية</th></tr>{hazmat}</table>"
                if hazmat
                else ""
            )
        )
    n = 4 if sheet.org else 3

    footer = print_footer.html(
        [
            "منصة ء-حماية · الديوان الوطني للحماية المدنية",
            f"أمر مهمة {sheet.number} · طُبع في {_local(sheet.printed_at)}",
            "وثيقة رسمية للاستعمال الداخلي، تُسلَّم إلى رئيس الفريق.",
        ],
        f"e-Himaya|أمر مهمة|{sheet.number}",
    )
    svg = map_svg(sheet)
    return f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<title>أمر مهمة {e(sheet.number)}</title><style>{_CSS}{print_footer.CSS}</style></head><body>
{footer}
<div class="head"><div class="state">الجمهورية التونسية<br>وزارة الداخلية<br>الديوان الوطني للحماية المدنية</div>
<div class="num">N° {e(sheet.number)}<br>{_local(sheet.issued_at)}</div></div>
<h1>أمر مهمة</h1>
<div class="sub">{e(nature)} · {e(sheet.delegation or "")} · {e(sheet.gouvernorat or "")}</div>
<div class="order">{e(sheet.order or "التوجه إلى مكان الحادث")}</div>
{alerts}
<h2>1. الحادث والبلاغ</h2><table>
{row("طبيعة الحادث", nature)}{row("العنوان المختصر", sheet.title)}
{row("المستوى العملياتي", LEVEL.get(sheet.level, sheet.level))}
{row("توقيت أول بلاغ", _local(sheet.first_report_at), True)}{row("توقيت إصدار الأمر", _local(sheet.issued_at), True)}
{row("المبلّغ", reporter)}{row("الهوية والهاتف", who)}{row("عدد البلاغات", sheet.report_count)}
{row("رقم الاتصال في عين المكان", sheet.contact_phone, True)}
</table>
<div class="small">ما قاله المبلّغون:</div><ul class="small">{texts}</ul>
<h2>2. مكان الحادث والمسلك</h2><table>
{row("الولاية", sheet.gouvernorat)}{row("المعتمدية", sheet.delegation)}{row("العمادة", sheet.sector)}
{row("البلدية", sheet.municipality)}{row("الإحداثيات", coords, True)}{row("المسلك", route_text)}
</table>
<div class="map">{svg}</div>
<div class="legend"><span class="b">● الوحدة</span> &nbsp; <span class="r">━ المسلك المتبع ━ ▼ مكان الحادث</span>
&nbsp; <span class="g">■ نقطة إخلاء</span> &nbsp; حدود المعتمدية بالأخضر الفاتح</div>
{org_html}
<h2>{n}. الفريق والوسيلة</h2><table>
{row("الوحدة", sheet.unit)}{row("هاتف الوحدة", sheet.unit_phone, True)}{row("الوسيلة ورقمها", vehicle)}
{row("رئيس الفريق", sheet.leader)}{row("الأعوان", sheet.crew_names)}{row("عدد الأعوان", sheet.crew_size)}
</table>
<h2>{n + 1}. تعليمات السلامة</h2><ul class="small">
<li>تأكيد الاستلام والتنقل والوصول من تطبيق الأعوان، أو باللاسلكي عند انقطاع الشبكة.</li>
<li>الاقتراب مع اتجاه الريح عند وجود دخان أو غاز، وارتداء أجهزة التنفس عند وجود مواد خطرة.</li>
<li>إعلام القاعة فورا بكل خطر على الفريق وطلب الدعم عند الحاجة.</li></ul>
<div class="sign"><div><b>رئيس الفريق</b>الاسم: {e(sheet.leader or "")}<br>الإمضاء:<br>التاريخ والساعة:</div>
<div><b>الضابط المناوب بالقاعة</b>الاسم:<br>الإمضاء والختم:</div></div>
</body></html>"""


def render_pdf(page: str) -> bytes:
    from weasyprint import HTML

    pdf: bytes = HTML(string=page).write_pdf()
    return pdf
