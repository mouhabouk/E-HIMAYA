"""SNACR queries (docs/phase-s/design-s.md): loading a year of the archive, the analysis of everyday risks and their
coverage, the register of specific risks and the plans."""

import json
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import as_system
from app.modules.geo.models import Delegation, Gouvernorat
from app.modules.settings import service as settings_service
from app.modules.settings.thresholds import SPECS
from app.modules.snacr import domain
from app.modules.snacr.models import Alias, Dataset, Plan, SpecialRisk

BATCH = 5_000

# ---------------------------------------------------------------- loading


async def places(session: AsyncSession) -> domain.Places:
    gouvernorats = (await session.execute(select(Gouvernorat.code, Gouvernorat.name_ar))).all()
    delegations = (await session.execute(select(Delegation.gouvernorat_code, Delegation.id, Delegation.name_ar))).all()
    aliases = (await session.execute(select(Alias.gouvernorat_code, Alias.raw, Alias.delegation_id))).all()
    return domain.places_from(
        [(c, n) for c, n in gouvernorats], [(g, d, n) for g, d, n in delegations], [(g, r, d) for g, r, d in aliases]
    )


_INSERT = text(
    """
INSERT INTO snacr.intervention (dataset_id, year, family, nature, subtype, gouvernorat_code, delegation_id,
    delegation_raw, called_at, departed_at, arrived_at, ended_at, arrival_min, flags)
SELECT CAST(:dataset AS uuid), CAST(:year AS smallint), u.family, u.nature, u.subtype, u.gouvernorat_code,
    u.delegation_id, u.delegation_raw, u.called_at, u.departed_at, u.arrived_at, u.ended_at, u.arrival_min,
    CASE WHEN u.flags = '' THEN '{}'::text[] ELSE string_to_array(u.flags, ',') END
FROM unnest(CAST(:family AS text[]), CAST(:nature AS text[]), CAST(:subtype AS text[]),
    CAST(:gouvernorat AS smallint[]), CAST(:delegation AS integer[]), CAST(:raw AS text[]),
    CAST(:called AS timestamptz[]), CAST(:departed AS timestamptz[]), CAST(:arrived AS timestamptz[]),
    CAST(:ended AS timestamptz[]), CAST(:arrival AS double precision[]), CAST(:flags AS text[]))
    AS u(family, nature, subtype, gouvernorat_code, delegation_id, delegation_raw, called_at, departed_at,
         arrived_at, ended_at, arrival_min, flags)
"""
)


async def _insert(session: AsyncSession, dataset: uuid.UUID, year: int, rows: list[domain.Row]) -> None:
    await session.execute(
        _INSERT,
        {
            "dataset": str(dataset),
            "year": year,
            "family": [r.family for r in rows],
            "nature": [r.nature for r in rows],
            "subtype": [r.subtype for r in rows],
            "gouvernorat": [r.gouvernorat_code for r in rows],
            "delegation": [r.delegation_id for r in rows],
            "raw": [r.delegation_raw for r in rows],
            "called": [r.called_at for r in rows],
            "departed": [r.departed_at for r in rows],
            "arrived": [r.arrived_at for r in rows],
            "ended": [r.ended_at for r in rows],
            "arrival": [r.arrival_min for r in rows],
            "flags": [",".join(r.flags) for r in rows],
        },
    )


async def load(
    session: AsyncSession,
    year: int,
    records: Iterable[dict[str, Any]],
    source: str,
    file_name: str | None,
    actor: str,
    actor_name: str | None,
) -> Dataset:
    """Replace the dataset of ``year`` with the cleaned ``records``; rows of another year are left out."""
    known = await places(session)
    quality = domain.Quality()
    await session.execute(delete(Dataset).where(Dataset.year == year))
    dataset = Dataset(
        id=uuid.uuid4(),
        year=year,
        source=source,
        simulated=source == "simulated",
        file_name=file_name,
        rows=0,
        quality={},
        imported_by=actor,
        imported_by_name=actor_name,
    )
    session.add(dataset)
    await session.flush()
    batch: list[domain.Row] = []
    for record in records:
        if quality.read >= domain.MAX_ROWS:
            raise domain.FileError("file_too_many_rows")
        row = domain.clean(record, known, quality)
        if row is None:
            continue
        if row.called_at.astimezone(domain.TUNIS).year != year:
            quality.kept -= 1
            quality.skip("other_year")
            continue
        batch.append(row)
        if len(batch) >= BATCH:
            await _insert(session, dataset.id, year, batch)
            batch = []
    if batch:
        await _insert(session, dataset.id, year, batch)
    if quality.kept == 0:
        raise domain.FileError("file_empty")
    dataset.rows = quality.kept
    dataset.quality = quality.out()
    await session.flush()
    return dataset


async def datasets(session: AsyncSession) -> list[Dataset]:
    return list((await session.scalars(select(Dataset).order_by(Dataset.year))).all())


async def years_available(session: AsyncSession) -> list[int]:
    return [d.year for d in await datasets(session)]


async def default_years(session: AsyncSession) -> list[int]:
    """The last three years loaded: the indicators rest on three consecutive years and move on each year."""
    return (await years_available(session))[-3:]


# ---------------------------------------------------------------- settings


async def method(session: AsyncSession) -> dict[str, Any]:
    t = {name: await settings_service.threshold(session, name) for name in SPECS if name.startswith("snacr.")}
    return {
        "goal": t["snacr.goal_percent"],
        "urban": t["snacr.density.urban"],
        "periurban": t["snacr.density.periurban"],
        "targets": {f: {z: t[f"snacr.target.{f}.{z}"] for z in domain.ZONES} for f in domain.FAMILIES},
        "review_months": t["snacr.review_months"],
        "validity_years": t["snacr.validity_years"],
    }


# ---------------------------------------------------------------- analysis

_ZONE = """CASE WHEN coalesce(dl.population_2024, 0) = 0 OR coalesce(dl.area_km2, 0) <= 0 THEN 'rural'
    WHEN dl.population_2024 / dl.area_km2 >= :urban THEN 'urban'
    WHEN dl.population_2024 / dl.area_km2 >= :periurban THEN 'periurban' ELSE 'rural' END"""
_VALID = f"i.arrival_min BETWEEN 0 AND {domain.ARRIVAL_CEILING_MIN}"
_DEPART = "EXTRACT(EPOCH FROM (i.departed_at - i.called_at)) / 60"
_TARGET = "CAST(CAST(:targets AS jsonb) #>> ARRAY[i.family, z.zone] AS double precision)"

_BY_DELEGATION = text(
    f"""
WITH z AS (SELECT dl.id, {_ZONE} AS zone FROM geo.delegation dl)
SELECT i.delegation_id, i.family, count(*) AS n,
    count(*) FILTER (WHERE i.arrival_min IS NOT NULL) AS recorded,
    count(*) FILTER (WHERE {_VALID}) AS valid,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY i.arrival_min) FILTER (WHERE {_VALID}) AS arrival_median,
    percentile_cont(0.9) WITHIN GROUP (ORDER BY i.arrival_min) FILTER (WHERE {_VALID}) AS arrival_p90,
    count(*) FILTER (WHERE {_VALID} AND i.arrival_min <= {_TARGET}) AS on_time,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY {_DEPART}) FILTER (WHERE {_DEPART} BETWEEN 0 AND 180)
        AS departure_median,
    percentile_cont(0.9) WITHIN GROUP (ORDER BY {_DEPART}) FILTER (WHERE {_DEPART} BETWEEN 0 AND 180)
        AS departure_p90
FROM snacr.intervention i JOIN z ON z.id = i.delegation_id
WHERE i.year = ANY(:years) AND (cardinality(CAST(:codes AS smallint[])) = 0 OR i.gouvernorat_code = ANY(:codes))
GROUP BY i.delegation_id, i.family
"""  # noqa: S608 (constants only, no input)
)
_BY_GOUVERNORAT = text(
    f"""
WITH z AS (SELECT dl.id, {_ZONE} AS zone FROM geo.delegation dl)
SELECT i.gouvernorat_code, i.family, count(*) AS n,
    count(*) FILTER (WHERE i.arrival_min IS NOT NULL) AS recorded,
    count(*) FILTER (WHERE {_VALID}) AS valid,
    count(*) FILTER (WHERE i.delegation_id IS NULL) AS unmatched,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY i.arrival_min) FILTER (WHERE {_VALID}) AS arrival_median,
    percentile_cont(0.9) WITHIN GROUP (ORDER BY i.arrival_min) FILTER (WHERE {_VALID}) AS arrival_p90,
    count(*) FILTER (WHERE {_VALID} AND z.zone IS NOT NULL AND i.arrival_min <= {_TARGET}) AS on_time,
    count(*) FILTER (WHERE {_VALID} AND z.zone IS NOT NULL) AS judged
FROM snacr.intervention i LEFT JOIN z ON z.id = i.delegation_id
WHERE i.year = ANY(:years) AND (cardinality(CAST(:codes AS smallint[])) = 0 OR i.gouvernorat_code = ANY(:codes))
GROUP BY i.gouvernorat_code, i.family
"""  # noqa: S608 (constants only, no input)
)
_NATIONAL_RATES = text(
    """
SELECT dl.id, count(i.id) AS n, dl.population_2024 AS population
FROM geo.delegation dl LEFT JOIN snacr.intervention i ON i.delegation_id = dl.id AND i.year = ANY(:years)
GROUP BY dl.id
"""
)
_BY_YEAR = text(
    """
SELECT i.year, i.family, count(*) AS n FROM snacr.intervention i
WHERE i.year = ANY(:years) AND (cardinality(CAST(:codes AS smallint[])) = 0 OR i.gouvernorat_code = ANY(:codes))
GROUP BY 1, 2 ORDER BY 1, 2
"""
)
_SEASONS = text(
    """
SELECT i.family, EXTRACT(MONTH FROM i.called_at AT TIME ZONE 'Africa/Tunis')::int AS month,
    EXTRACT(ISODOW FROM i.called_at AT TIME ZONE 'Africa/Tunis')::int AS weekday,
    EXTRACT(HOUR FROM i.called_at AT TIME ZONE 'Africa/Tunis')::int AS hour, count(*) AS n
FROM snacr.intervention i
WHERE i.year = ANY(:years) AND (cardinality(CAST(:codes AS smallint[])) = 0 OR i.gouvernorat_code = ANY(:codes))
GROUP BY 1, 2, 3, 4
"""
)
_SUBTYPES = text(
    """
SELECT i.family, coalesce(i.subtype, '') AS subtype, count(*) AS n FROM snacr.intervention i
WHERE i.year = ANY(:years) AND (cardinality(CAST(:codes AS smallint[])) = 0 OR i.gouvernorat_code = ANY(:codes))
GROUP BY 1, 2 ORDER BY 3 DESC
"""
)


def _pct(part: int, whole: int) -> float | None:
    return round(100 * part / whole, 1) if whole else None


def _round(value: Any) -> float | None:
    return round(float(value), 1) if value is not None else None


def _figures(n: int, recorded: int, valid: int, on_time: int, judged: int) -> dict[str, Any]:
    return {
        "rows": n,
        "completeness_pct": _pct(valid, n),
        "recorded_pct": _pct(recorded, n),
        "compliance_pct": _pct(on_time, judged),
    }


async def analysis(session: AsyncSession, codes: list[int], years: list[int]) -> dict[str, Any]:
    """Everyday risks and their coverage over ``years`` for ``codes`` (``[]``: the whole country)."""
    m = await method(session)
    params = {
        "years": years,
        "codes": codes,
        "urban": m["urban"],
        "periurban": m["periurban"],
        "targets": json.dumps(m["targets"]),
    }
    span = max(1, len(years))
    # The frequency level compares a délégation with the whole country, whatever the caller may read: counts only.
    async with as_system(session) as system:
        national = (await system.execute(_NATIONAL_RATES, {"years": years})).all()
    national_rates = {d: 1000 * n / span / pop for d, n, pop in national if pop and n}
    breaks = domain.quintile_breaks(list(national_rates.values()))

    names = {
        d.id: d
        for d in (
            await session.scalars(
                select(Delegation).where(Delegation.gouvernorat_code.in_(codes)) if codes else select(Delegation)
            )
        ).all()
    }
    delegations: dict[int, dict[str, Any]] = {}
    for row in (await session.execute(_BY_DELEGATION, params)).mappings():
        d = names.get(row["delegation_id"])
        if d is None:
            continue
        entry = delegations.setdefault(
            d.id,
            {
                "id": d.id,
                "gouvernorat_code": d.gouvernorat_code,
                "name_ar": d.name_ar,
                "name_fr": d.name_fr,
                "population": d.population_2024,
                "area_km2": round(d.area_km2, 1) if d.area_km2 else None,
                "zone": domain.zone_of(d.population_2024, d.area_km2, m["urban"], m["periurban"]),
                "families": {},
                "_n": 0,
                "_recorded": 0,
                "_valid": 0,
                "_on_time": 0,
            },
        )
        entry["families"][row["family"]] = {
            **_figures(row["n"], row["recorded"], row["valid"], row["on_time"], row["valid"]),
            "arrival_median": _round(row["arrival_median"]),
            "arrival_p90": _round(row["arrival_p90"]),
            "departure_median": _round(row["departure_median"]),
            "departure_p90": _round(row["departure_p90"]),
            "target": m["targets"][row["family"]][entry["zone"]],
        }
        entry["_n"] += row["n"]
        entry["_recorded"] += row["recorded"]
        entry["_valid"] += row["valid"]
        entry["_on_time"] += row["on_time"]
    matrix = [[0] * 5 for _ in range(5)]
    out_delegations = []
    for entry in delegations.values():
        n, recorded, valid, on_time = (entry.pop(k) for k in ("_n", "_recorded", "_valid", "_on_time"))
        rate = 1000 * n / span / entry["population"] if entry["population"] else None
        compliance = _pct(on_time, valid)
        frequency = domain.frequency_level(rate, breaks)
        coverage = domain.coverage_level(compliance, m["goal"])
        entry.update(
            {
                **_figures(n, recorded, valid, on_time, valid),
                "annual": round(n / span),
                "rate_per_1000": round(rate, 2) if rate is not None else None,
                "frequency_level": frequency,
                "coverage_level": coverage,
                "priority": domain.priority_of(frequency, coverage),
            }
        )
        if frequency and coverage:
            matrix[frequency - 1][coverage - 1] += 1
        out_delegations.append(entry)
    out_delegations.sort(key=lambda e: (e["gouvernorat_code"], e["id"]))

    gouvernorats: dict[int, dict[str, Any]] = {}
    population = dict((await session.execute(select(Gouvernorat.code, Gouvernorat.population_2024))).all())
    for row in (await session.execute(_BY_GOUVERNORAT, params)).mappings():
        g = gouvernorats.setdefault(
            row["gouvernorat_code"],
            {
                "code": row["gouvernorat_code"],
                "families": {},
                "_n": 0,
                "_rec": 0,
                "_val": 0,
                "_ok": 0,
                "_jud": 0,
                "_unm": 0,
            },
        )
        g["families"][row["family"]] = {
            **_figures(row["n"], row["recorded"], row["valid"], row["on_time"], row["judged"]),
            "arrival_median": _round(row["arrival_median"]),
            "arrival_p90": _round(row["arrival_p90"]),
        }
        for key, col in (
            ("_n", "n"),
            ("_rec", "recorded"),
            ("_val", "valid"),
            ("_ok", "on_time"),
            ("_jud", "judged"),
            ("_unm", "unmatched"),
        ):
            g[key] += row[col]
    totals = {"n": 0, "rec": 0, "val": 0, "ok": 0, "jud": 0, "unm": 0}
    out_gouvernorats = []
    for g in sorted(gouvernorats.values(), key=lambda x: x["code"]):
        n, rec, val, ok, jud, unm = (g.pop(k) for k in ("_n", "_rec", "_val", "_ok", "_jud", "_unm"))
        for key, value in zip(totals, (n, rec, val, ok, jud, unm), strict=True):
            totals[key] += value
        pop = population.get(g["code"])
        g.update(
            {
                **_figures(n, rec, val, ok, jud),
                "unmatched": unm,
                "annual": round(n / span),
                "rate_per_1000": round(1000 * n / span / pop, 2) if pop else None,
            }
        )
        out_gouvernorats.append(g)
    scope_population = sum(population.get(c, 0) or 0 for c in (codes or population.keys()))

    by_year: dict[int, dict[str, int]] = {}
    for year, family, n in await session.execute(_BY_YEAR, params):
        by_year.setdefault(year, {})[family] = n
    month = {f: [0] * 12 for f in domain.FAMILIES}
    weekday_hour = {f: [[0] * 24 for _ in range(7)] for f in domain.FAMILIES}
    for family, mo, wd, hour, n in await session.execute(_SEASONS, params):
        month[family][mo - 1] += n
        weekday_hour[family][wd - 1][hour] += n
    subtypes: dict[str, list[dict[str, Any]]] = {f: [] for f in domain.FAMILIES}
    for family, subtype, n in await session.execute(_SUBTYPES, params):
        if subtype and len(subtypes[family]) < 10:
            subtypes[family].append({"subtype": subtype, "rows": n})
    used = [d for d in await datasets(session) if d.year in years]
    return {
        "years": years,
        "codes": codes,
        "simulated": any(d.simulated for d in used),
        "datasets": [{"year": d.year, "simulated": d.simulated, "rows": d.rows} for d in used],
        "method": m,
        "breaks": [round(b, 2) for b in breaks],
        "totals": {
            **_figures(totals["n"], totals["rec"], totals["val"], totals["ok"], totals["jud"]),
            "unmatched": totals["unm"],
            "annual": round(totals["n"] / span),
            "population": scope_population or None,
            "rate_per_1000": round(1000 * totals["n"] / span / scope_population, 2) if scope_population else None,
        },
        "by_year": [{"year": y, "families": f} for y, f in sorted(by_year.items())],
        "gouvernorats": out_gouvernorats,
        "delegations": out_delegations,
        "matrix": matrix,
        "month": month,
        "weekday_hour": weekday_hour,
        "subtypes": subtypes,
    }


# ---------------------------------------------------------------- aliases and unmatched names


async def unmatched(session: AsyncSession, codes: list[int]) -> list[dict[str, Any]]:
    stmt = text(
        """
SELECT i.gouvernorat_code, i.delegation_raw, count(*) AS n FROM snacr.intervention i
WHERE i.delegation_id IS NULL AND (cardinality(CAST(:codes AS smallint[])) = 0 OR i.gouvernorat_code = ANY(:codes))
GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 500
"""
    )
    return [
        {"gouvernorat_code": g, "raw": raw, "rows": n} for g, raw, n in (await session.execute(stmt, {"codes": codes}))
    ]


async def add_alias(
    session: AsyncSession, gouvernorat: int, raw: str, delegation_id: int, actor: str, actor_name: str | None
) -> tuple[Alias, int]:
    """Record the name and give its délégation to the rows of the archive that carried it; returns the rows fixed."""
    delegation = await session.get(Delegation, delegation_id)
    if delegation is None or delegation.gouvernorat_code != gouvernorat:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "delegation_not_in_gouvernorat")
    normalized = domain.normalize(raw)
    if not normalized:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "alias_empty")
    exists = await session.scalar(
        select(Alias).where(Alias.gouvernorat_code == gouvernorat, Alias.normalized == normalized)
    )
    if exists is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "alias_exists")
    alias = Alias(
        gouvernorat_code=gouvernorat,
        raw=raw.strip(),
        normalized=normalized,
        delegation_id=delegation_id,
        created_by=actor,
        created_by_name=actor_name,
    )
    session.add(alias)
    raws = (
        (
            await session.execute(
                text(
                    "SELECT DISTINCT delegation_raw FROM snacr.intervention "
                    "WHERE gouvernorat_code = :g AND delegation_id IS NULL"
                ),
                {"g": gouvernorat},
            )
        )
        .scalars()
        .all()
    )
    same = [r for r in raws if domain.normalize(r) == normalized]
    fixed = 0
    if same:
        result = await session.execute(
            text(
                "UPDATE snacr.intervention SET delegation_id = :d, "
                "flags = array_remove(flags, 'delegation_unmatched') "
                "WHERE gouvernorat_code = :g AND delegation_id IS NULL AND delegation_raw = ANY(:raws)"
            ),
            {"d": delegation_id, "g": gouvernorat, "raws": same},
        )
        fixed = int(getattr(result, "rowcount", 0) or 0)
    await session.flush()
    return alias, fixed


async def aliases(session: AsyncSession, codes: list[int]) -> list[Alias]:
    stmt = select(Alias).order_by(Alias.gouvernorat_code, Alias.raw)
    if codes:
        stmt = stmt.where(Alias.gouvernorat_code.in_(codes))
    return list((await session.scalars(stmt)).all())


# ---------------------------------------------------------------- specific risks


async def special_risks(session: AsyncSession, codes: list[int]) -> list[SpecialRisk]:
    stmt = select(SpecialRisk).order_by(SpecialRisk.gouvernorat_code, SpecialRisk.hazard)
    if codes:
        stmt = stmt.where(SpecialRisk.gouvernorat_code.in_(codes))
    return list((await session.scalars(stmt)).all())


def special_out(risk: SpecialRisk) -> dict[str, Any]:
    return {
        "id": str(risk.id),
        "gouvernorat_code": risk.gouvernorat_code,
        "hazard": risk.hazard,
        "probability": risk.probability,
        "gravity": risk.gravity,
        "level": domain.special_level(risk.probability, risk.gravity),
        "note": risk.note,
        "simulated": risk.simulated,
        "updated_by_name": risk.updated_by_name,
        "updated_at": risk.updated_at.isoformat() if risk.updated_at else None,
    }


# ---------------------------------------------------------------- plans


def objectives(content: dict[str, Any]) -> list[dict[str, Any]]:
    """What the plan commits to, drawn from the analysis: the délégations of high priority, the gouvernorats whose
    archive is too incomplete to judge, and the specific risks of high level."""
    out: list[dict[str, Any]] = []
    a = content["analysis"]
    goal = a["method"]["goal"]
    for d in sorted(
        (d for d in a["delegations"] if d["priority"] == "high"),
        key=lambda d: (-(d["frequency_level"] or 0) * (d["coverage_level"] or 0), -d["rows"]),
    ):
        worst = min(
            ((f, v) for f, v in d["families"].items() if v["compliance_pct"] is not None and v["rows"] >= 30),
            key=lambda fv: fv[1]["compliance_pct"],
            default=None,
        )
        if worst is None:
            continue
        family, v = worst
        out.append(
            {
                "kind": "coverage",
                "gouvernorat_code": d["gouvernorat_code"],
                "delegation_id": d["id"],
                "delegation": d["name_ar"],
                "family": family,
                "target_min": v["target"],
                "from_pct": v["compliance_pct"],
                "to_pct": goal,
            }
        )
    for g in a["gouvernorats"]:
        if (g["completeness_pct"] or 0) < 80:
            out.append({"kind": "data", "gouvernorat_code": g["code"], "from_pct": g["completeness_pct"], "to_pct": 95})
        if g["unmatched"]:
            out.append({"kind": "names", "gouvernorat_code": g["code"], "rows": g["unmatched"]})
    for r in content["special_risks"]:
        if r["level"] == "high":
            out.append({"kind": "special", "gouvernorat_code": r["gouvernorat_code"], "hazard": r["hazard"]})
    return out


async def build_plan(
    session: AsyncSession, gouvernorat: int | None, years: list[int], actor: str, actor_name: str | None
) -> Plan:
    codes = [gouvernorat] if gouvernorat is not None else []
    result = await analysis(session, codes, years)
    content: dict[str, Any] = {
        "analysis": result,
        "special_risks": [special_out(r) for r in await special_risks(session, codes)],
        "references": list(domain.REFERENCES),
        "quality": [
            {"year": d.year, "simulated": d.simulated, "rows": d.rows, "quality": d.quality}
            for d in await datasets(session)
            if d.year in years
        ],
    }
    content["objectives"] = objectives(content)
    version = (
        await session.scalar(
            select(func.coalesce(func.max(Plan.version), 0)).where(
                Plan.gouvernorat_code.is_(None) if gouvernorat is None else Plan.gouvernorat_code == gouvernorat
            )
        )
        or 0
    ) + 1
    plan = Plan(
        gouvernorat_code=gouvernorat,
        version=version,
        years=years,
        status="draft",
        simulated=result["simulated"] or any(r["simulated"] for r in content["special_risks"]),
        content=content,
        created_by=actor,
        created_by_name=actor_name,
    )
    session.add(plan)
    await session.flush()
    return plan


async def approve(session: AsyncSession, plan: Plan, actor: str, actor_name: str | None) -> None:
    if plan.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "plan_not_draft")
    await session.execute(
        text(
            "UPDATE snacr.plan SET status = 'superseded' WHERE status = 'approved' "
            "AND coalesce(gouvernorat_code, 0) = coalesce(CAST(:g AS smallint), 0)"
        ),
        {"g": plan.gouvernorat_code},
    )
    plan.status = "approved"
    plan.approved_by = actor
    plan.approved_by_name = actor_name
    plan.approved_at = datetime.now(UTC)
    await session.flush()
