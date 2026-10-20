"""Fire spread and flood advisory runs of an incident (docs/api/phase-7-contract.md §2, docs/weather-forecast.md).

Each run reads the weather of the incident's nearest grid point and the terrain model, records every input and
assumption with the result in ``forecast.run``, and carries a disclaimer: these are aids to a human decision, never
an instruction.
"""

import json
import math
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.forecast import flood, rothermel, schemas
from app.modules.forecast.models import ForecastRun
from app.modules.forecast.terrain import get_terrain, slope_at
from app.modules.forecast.terrain_fetch import ATTRIBUTION as TERRAIN_ATTRIBUTION
from app.modules.ops.models import Incident
from app.modules.weather import fwi
from app.modules.weather import service as weather
from app.modules.weather.models import GridPoint, Observation

FIRE_MODEL = "rothermel-elliptical-v1"
FLOOD_MODEL = "rain-terrain-advisory-v1"
# Contract fuel classes → Anderson (1982) fuel models, chosen for Tunisian vegetation (docs/weather-forecast.md).
FUELS: dict[str, tuple[int, float | None]] = {
    "grass": (1, None),  # short grass, cereal stubble
    "shrub": (4, None),  # maquis and garrigue (chaparral-like)
    "timber_litter": (9, 0.15),  # Aleppo pine / cork oak litter under a partial canopy (sheltered wind factor)
    "mixed": (2, None),  # open woodland with grass and shrub understory
}
DEFAULT_FUEL = "mixed"
FLOOD_RADIUS_M = 3000.0
DRY_MONTHS = (6, 7, 8, 9)

FIRE_DISCLAIMER = {
    "ar": "تقدير آلي لانتشار الحريق (نموذج روثرميل مع شكل إهليلجي) انطلاقًا من الطقس والتضاريس وافتراضات مذكورة. "
    "هو مساعدة على القرار وليس أمرًا: قد يختلف الحريق الحقيقي كثيرًا (الرياح المحلية، نوع الغطاء النباتي، "
    "التدخلات). القرار يعود دائمًا إلى المسؤول.",
    "fr": "Estimation automatique de la propagation (modèle de Rothermel, forme elliptique) à partir de la météo, du "
    "relief et des hypothèses listées. C'est une aide à la décision, pas une consigne : le feu réel peut s'en écarter "
    "fortement (vent local, végétation, interventions). La décision appartient toujours au responsable.",
}
FLOOD_DISCLAIMER = {
    "ar": "تنبيه استشاري وليس نموذجًا هيدروليكيًا: يجمع كميات الأمطار المرصودة والمتوقعة مع المناطق المنخفضة "
    "واتجاه التصريف في نموذج التضاريس. لا يحسب منسوب المياه ولا السدود ولا شبكات التصريف. القرار يعود إلى المسؤول.",
    "fr": "Avis consultatif, pas un modèle hydraulique : il combine la pluie observée et prévue avec les points bas et "
    "le sens d'écoulement du modèle de terrain. Il ne calcule ni hauteurs d'eau, ni barrages, ni réseaux "
    "d'assainissement. La décision appartient au responsable.",
}

ASSUMPTIONS: dict[str, dict[str, str]] = {
    "no_terrain": {
        "ar": "نموذج التضاريس غير مثبّت: اعتُبر الانحدار صفرًا.",
        "fr": "Modèle de terrain non installé : pente supposée nulle.",
    },
    "default_fuel": {
        "ar": "لا توجد طبقة غطاء نباتي: استُعمل نموذج الوقود «مختلط» (أندرسون 2).",
        "fr": "Pas de couche d'occupation du sol : combustible « mixte » (Anderson 2) retenu.",
    },
    "uniform_conditions": {
        "ar": "الطقس والوقود والانحدار عند نقطة الاشتعال مفترضة ثابتة على كامل المساحة وطوال المدة.",
        "fr": "Météo, combustible et pente du point d'éclosion supposés uniformes sur la zone et dans le temps.",
    },
    "dead_moisture_from_ffmc": {
        "ar": "رطوبة الوقود الميت من مؤشر FFMC لليوم (+1٪ و+2٪ للأقطار الأكبر).",
        "fr": "Humidité des combustibles morts tirée du FFMC du jour (+1 % et +2 % pour les classes 10 h et 100 h).",
    },
    "dead_moisture_default": {
        "ar": "لا يتوفر مؤشر FFMC: رطوبة الوقود الميت مفترضة 8٪.",
        "fr": "FFMC indisponible : humidité des combustibles morts supposée de 8 %.",
    },
    "live_moisture_season": {
        "ar": "رطوبة الوقود الحي مفترضة حسب الفصل (80٪ صيفًا، 120٪ في باقي السنة).",
        "fr": "Humidité des combustibles vivants supposée selon la saison (80 % l'été, 120 % le reste de l'année).",
    },
    "wind_10m_to_midflame": {
        "ar": "الرياح على ارتفاع 10 م محوّلة إلى مستوى اللهب بمعامل تعديل الرياح للنموذج.",
        "fr": "Vent à 10 m ramené à mi-flamme par le facteur d'ajustement du modèle de combustible.",
    },
    "wind_limit": {
        "ar": "طُبّق حدّ سرعة الرياح في نموذج روثرميل (Andrews وآخرون 2013).",
        "fr": "La limite de vent du modèle de Rothermel a été appliquée (Andrews et al. 2013).",
    },
    "no_suppression": {
        "ar": "لا يأخذ في الحسبان أي تدخل للإطفاء ولا الحواجز (طرقات، أودية).",
        "fr": "Ne tient compte d'aucune action de lutte ni des coupures (routes, oueds).",
    },
    "ignition_centroid": {
        "ar": "نقطة الاشتعال هي مركز الحادث.",
        "fr": "Le point d'éclosion est le centre de l'incident.",
    },
    "simulated_weather": {
        "ar": "[محاكاة] الطقس المستعمل مُحاكى وليس بيانات حقيقية.",
        "fr": "[SIM] Météo simulée, pas des données réelles.",
    },
    "flood_area_circle": {
        "ar": "منطقة الحادث غير محددة: حُلّلت دائرة نصف قطرها 3 كم حول مركزه.",
        "fr": "Zone de l'incident non définie : cercle de 3 km de rayon autour de son centre analysé.",
    },
    "flood_point_rain": {
        "ar": "الأمطار هي أمطار أقرب نقطة من شبكة الطقس، مفترضة متجانسة على المنطقة.",
        "fr": "Pluie du point de grille météo le plus proche, supposée homogène sur la zone.",
    },
    "flood_no_terrain": {
        "ar": "نموذج التضاريس غير مثبّت: منطقة الخطر هي منطقة الحادث بأكملها دون نقاط منخفضة.",
        "fr": "Modèle de terrain non installé : la zone de risque est toute la zone, sans points bas.",
    },
    "flood_no_hydraulics": {
        "ar": "لا يحسب التدفق في الأودية ولا قدرة التصريف ولا تشبّع التربة.",
        "fr": "Ne calcule ni débit des oueds, ni capacité d'évacuation, ni saturation des sols.",
    },
    "flood_dsm": {
        "ar": "نموذج التضاريس نموذج سطح (يشمل المباني والأشجار) بدقة 90 م.",
        "fr": "Le modèle de terrain est un modèle de surface (bâtiments, arbres) à 90 m.",
    },
}


def _assumption(code: str) -> dict[str, Any]:
    return {"code": code, "text": ASSUMPTIONS[code]}


async def _centroid(session: AsyncSession, incident: Incident) -> tuple[float, float] | None:
    row = (
        await session.execute(
            select(func.ST_Y(cast(Incident.centroid, Geometry)), func.ST_X(cast(Incident.centroid, Geometry))).where(
                Incident.id == incident.id, Incident.centroid.is_not(None)
            )
        )
    ).first()
    return None if row is None else (float(row[0]), float(row[1]))


async def _area_ring(session: AsyncSession, incident: Incident) -> list[list[float]] | None:
    if incident.area is None:
        return None
    raw = await session.scalar(
        select(func.ST_AsGeoJSON(cast(Incident.area, Geometry), 6)).where(Incident.id == incident.id)
    )
    if raw is None:
        return None
    coordinates = json.loads(raw).get("coordinates") or []
    return coordinates[0] if coordinates else None


async def _weather_now(session: AsyncSession, lat: float, lon: float) -> tuple[GridPoint, Observation]:
    point = await weather.nearest_point(session, lat, lon)
    if point is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "weather_unavailable")
    now = datetime.now(UTC)
    hour = now.replace(minute=0, second=0, microsecond=0)
    rows = await weather.series_of(session, point.id, hour - timedelta(hours=3), hour + timedelta(hours=1))
    current = weather.current_of(rows, now)
    if current is None or current.wind_speed_kmh is None or current.relative_humidity_pct is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "weather_unavailable")
    return point, current


def _attribution(simulated: bool, terrain_used: bool) -> list[str]:
    weather_attr = weather.attribution(simulated)
    out = [weather_attr if isinstance(weather_attr, str) else f"{weather_attr['text']} ({weather_attr['licence']})"]
    if terrain_used:
        out.append(TERRAIN_ATTRIBUTION)
    return out


async def _store(
    session: AsyncSession,
    incident: Incident,
    kind: str,
    model: str,
    out: dict[str, Any],
    actor: str,
    simulated: bool,
) -> uuid.UUID:
    run = ForecastRun(
        id=uuid.UUID(out["forecast_id"]),
        incident_id=incident.id,
        kind=kind,
        model=model,
        inputs=out["inputs"],
        result=out,
        assumptions=out["assumptions"],
        simulated=simulated,
        created_by=actor,
    )
    session.add(run)
    await session.flush()
    return run.id


async def fire(
    session: AsyncSession, incident: Incident, body: schemas.FireForecastIn, actor: str
) -> schemas.FireForecastOut:
    assumptions: list[dict[str, Any]] = []
    if body.ignition is not None:
        lat, lon = body.ignition.lat, body.ignition.lon
    else:
        centroid = await _centroid(session, incident)
        if centroid is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "incident_without_location")
        lat, lon = centroid
        assumptions.append(_assumption("ignition_centroid"))
    point, obs = await _weather_now(session, lat, lon)

    fuel_key = body.fuel_model or DEFAULT_FUEL
    if body.fuel_model is None:
        assumptions.append(_assumption("default_fuel"))
    number, sheltered_waf = FUELS[fuel_key]
    model = rothermel.FUEL_MODELS[number]

    if obs.ffmc is not None:
        dead = fwi.ffmc_to_moisture(obs.ffmc) / 100.0
        assumptions.append(_assumption("dead_moisture_from_ffmc"))
    else:
        dead = 0.08
        assumptions.append(_assumption("dead_moisture_default"))
    month = (obs.at + timedelta(hours=1)).month
    live = 0.8 if month in DRY_MONTHS else 1.2
    assumptions.append(_assumption("live_moisture_season"))
    moisture = rothermel.Moisture(
        dead_1h=dead, dead_10h=dead + 0.01, dead_100h=dead + 0.02, live_herb=live, live_woody=live
    )

    terrain = get_terrain()
    slope = slope_at(terrain, lat, lon) if terrain is not None else None
    if slope is None:
        assumptions.append(_assumption("no_terrain"))
    wind_kmh = obs.wind_speed_kmh or 0.0
    wind_from = obs.wind_direction_deg or 0.0
    midflame = rothermel.midflame_wind_mph(wind_kmh, model, sheltered=sheltered_waf)
    assumptions.append(_assumption("wind_10m_to_midflame"))
    result = rothermel.spread(
        model,
        moisture,
        midflame,
        wind_towards_deg=(wind_from + 180.0) % 360.0,
        slope_fraction=slope.slope_fraction if slope else 0.0,
        upslope_deg=slope.upslope_deg if slope else 0.0,
    )
    if result.wind_limited:
        assumptions.append(_assumption("wind_limit"))
    assumptions += [_assumption("uniform_conditions"), _assumption("no_suppression")]
    if point.simulated:
        assumptions.append(_assumption("simulated_weather"))

    polygons = []
    for minutes in body.horizons_min:
        shape = rothermel.ellipse(result, minutes)
        polygons.append(
            {
                "minutes": minutes,
                "geojson": {"type": "Polygon", "coordinates": [shape.ring(lat, lon)]},
                "area_ha": round(shape.area_ha, 2),
                "head_m": round(shape.head_m),
                "back_m": round(shape.back_m),
                "length_m": round(shape.length_m),
                "width_m": round(shape.width_m),
            }
        )
    inputs = {
        "ignition": {"lat": lat, "lon": lon},
        "weather_point": {
            "lat": point.lat,
            "lon": point.lon,
            "distance_km": weather.distance_km(lat, lon, point.lat, point.lon),
        },
        "weather_at": obs.at.isoformat(),
        "wind": {
            "speed_kmh": wind_kmh,
            "gust_kmh": obs.wind_gust_kmh,
            "direction_deg": wind_from,
            "midflame_kmh": round(midflame / rothermel.KMH_TO_MPH, 1),
            "adjustment_factor": sheltered_waf if sheltered_waf is not None else model.waf,
        },
        "rh": obs.relative_humidity_pct,
        "temp": obs.temperature_c,
        "ffmc": None if obs.ffmc is None else round(obs.ffmc, 1),
        "fire_danger": obs.fire_danger,
        "slope_pct": round(slope.slope_pct, 1) if slope else 0.0,
        "upslope_deg": round(slope.upslope_deg) if slope else None,
        "elevation_m": slope.elevation_m if slope else None,
        "fuel": {"key": fuel_key, "anderson": number, "name": model.name},
        "moisture_pct": {
            "dead_1h": round(dead * 100, 1),
            "dead_10h": round(dead * 100 + 1, 1),
            "dead_100h": round(dead * 100 + 2, 1),
            "live": round(live * 100),
        },
        "horizons_min": body.horizons_min,
    }
    simulated = point.simulated
    out = {
        "forecast_id": str(uuid.uuid4()),
        "incident_id": str(incident.id),
        "kind": "fire",
        "model": FIRE_MODEL,
        "inputs": inputs,
        "polygons": polygons,
        "rate_of_spread_m_min": round(result.ros_m_min, 2),
        "backing_rate_m_min": round(result.backing_m_min, 2),
        "heading_deg": round(result.heading_deg),
        "length_to_breadth": round(result.length_to_breadth, 2),
        "fireline_intensity_kw_m": round(result.fireline_intensity_kw_m),
        "flame_length_m": round(result.flame_length_m, 1),
        "assumptions": assumptions,
        "disclaimer": FIRE_DISCLAIMER,
        "attribution": _attribution(simulated, slope is not None),
        "generated_at": datetime.now(UTC).isoformat(),
        "created_by": actor,
        "simulated": simulated,
    }
    await _store(session, incident, "fire", FIRE_MODEL, out, actor, simulated)
    return schemas.FireForecastOut.model_validate(out)


async def _rain(session: AsyncSession, point: GridPoint, current: Observation) -> flood.Rain:
    start = current.at
    rows = await weather.series_of(session, point.id, start + timedelta(hours=1), start + timedelta(hours=24))

    def total(hours: int) -> float:
        return round(sum(o.precipitation_mm or 0.0 for o in rows if o.at <= start + timedelta(hours=hours)), 1)

    return flood.Rain(
        observed_24h_mm=round(current.precipitation_24h_mm or 0.0, 1),
        next_6h_mm=total(6),
        next_12h_mm=total(12),
        next_24h_mm=total(24),
        max_1h_mm=round(max([current.precipitation_mm or 0.0, *(o.precipitation_mm or 0.0 for o in rows)]), 1),
    )


async def flood_advisory(session: AsyncSession, incident: Incident, actor: str) -> schemas.FloodForecastOut:
    centroid = await _centroid(session, incident)
    ring = await _area_ring(session, incident)
    if centroid is None and ring is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "incident_without_location")
    assumptions: list[dict[str, Any]] = []
    if ring is not None:
        lons, lats = [p[0] for p in ring], [p[1] for p in ring]
        lat, lon = (min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2
        half_height = (max(lats) - min(lats)) / 2 * 111_320.0
        half_width = (max(lons) - min(lons)) / 2 * 111_320.0 * math.cos(math.radians(lat))
        radius = max(half_height, half_width, 500.0)
    else:
        assert centroid is not None
        lat, lon = centroid
        radius = FLOOD_RADIUS_M
        assumptions.append(_assumption("flood_area_circle"))
    point, current = await _weather_now(session, lat, lon)
    rain = await _rain(session, point, current)
    assumptions.append(_assumption("flood_point_rain"))

    terrain = get_terrain()
    analysis = flood.analyse(terrain, lat, lon, radius) if terrain is not None else None
    area_ring = ring or flood.circle(lat, lon, radius)
    risk_ring = flood.polygon(analysis.low_area) if analysis is not None else None
    if analysis is None:
        assumptions.append(_assumption("flood_no_terrain"))
    else:
        assumptions.append(_assumption("flood_dsm"))
    assumptions.append(_assumption("flood_no_hydraulics"))
    if point.simulated:
        assumptions.append(_assumption("simulated_weather"))
    risk_ring = risk_ring or area_ring
    level = flood.level(rain)
    simulated = point.simulated
    inputs: dict[str, Any] = {
        "center": {"lat": round(lat, 5), "lon": round(lon, 5)},
        "radius_m": round(radius),
        "weather_point": {
            "lat": point.lat,
            "lon": point.lon,
            "distance_km": weather.distance_km(lat, lon, point.lat, point.lon),
        },
        "weather_at": current.at.isoformat(),
        "rain": {
            "observed_24h_mm": rain.observed_24h_mm,
            "next_6h_mm": rain.next_6h_mm,
            "next_12h_mm": rain.next_12h_mm,
            "next_24h_mm": rain.next_24h_mm,
            "max_1h_mm": rain.max_1h_mm,
            "total_mm": round(rain.total_mm, 1),
        },
        "heavy_rain": current.heavy_rain,
        "level_thresholds": [{"level": n, "total_mm": t, "max_1h_mm": h} for n, t, h in flood.LEVELS],
    }
    if analysis is not None:
        inputs["terrain"] = {
            "center_elevation_m": analysis.center_elevation_m,
            "min_elevation_m": analysis.min_elevation_m,
            "max_elevation_m": analysis.max_elevation_m,
            "mean_slope_pct": analysis.mean_slope_pct,
        }
    out = {
        "forecast_id": str(uuid.uuid4()),
        "incident_id": str(incident.id),
        "kind": "flood",
        "model": FLOOD_MODEL,
        "advisory": True,
        "inputs": inputs,
        "level": level,
        "risk_polygon": {"type": "Polygon", "coordinates": [risk_ring]},
        "risk_area_ha": round(flood.ring_area_ha(risk_ring), 1),
        "low_points": [
            {"lat": p[0], "lon": p[1], "elevation_m": p[2]} for p in (analysis.low_points if analysis else [])
        ],
        "drainage_direction_deg": analysis.drainage_direction_deg if analysis else None,
        "assumptions": assumptions,
        "disclaimer": FLOOD_DISCLAIMER,
        "attribution": _attribution(simulated, analysis is not None),
        "generated_at": datetime.now(UTC).isoformat(),
        "created_by": actor,
        "simulated": simulated,
    }
    await _store(session, incident, "flood", FLOOD_MODEL, out, actor, simulated)
    return schemas.FloodForecastOut.model_validate(out)


async def runs(session: AsyncSession, incident: Incident, limit: int) -> list[dict[str, Any]]:
    rows = await session.scalars(
        select(ForecastRun)
        .where(ForecastRun.incident_id == incident.id)
        .order_by(ForecastRun.created_at.desc())
        .limit(limit)
    )
    return [r.result for r in rows]
