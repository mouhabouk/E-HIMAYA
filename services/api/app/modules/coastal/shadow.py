"""The drowning risk model kept in shadow beside the declared rules (docs/phase-l/design-l5.md §4.2, backlog S3).

A logistic regression (scikit-learn) learns the chance of a drowning on a beach-day from the same inputs as the rules
(risk.py): waves, current, onshore wind, heat, season, crowd, lifeguards and past drownings. Tunisia has no open
record of drownings per beach and day, so it is trained on **[SIM]** beach-days drawn from a declared process
(:func:`simulate`), and the card says so. It is stored as plain coefficients (no pickle, nothing executable) and
applied in pure Python by the daily computation, which writes its probability and level beside the rule's.

The shadow never reaches the public, never opens an alert and never changes the rule's level. Its levels are cut so
that it flags as many beach-days as the rules do on the same training days: the comparison is then about *which*
days are flagged, not how many. Whether it may ever replace the rules is the committee's decision (AI-01).

    python -m app.modules.coastal.shadow [--seed 7]    # trains a new version as the system
"""

import argparse
import asyncio
import math
import random
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.coastal import risk
from app.modules.coastal.models import BeachDay, RiskModel

ALGORITHM = "scikit-learn 1.9 LogisticRegression"
FEATURES = (
    "waves_m",
    "waves_over_1_5_m",
    "current_kmh",
    "onshore_kmh",
    "heat_over_28_c",
    "season",
    "crowd_high",
    "unguarded_in_season",
    "past_drownings",
)
TRAIN_DAYS = 30_000
TEST_DAYS = 10_000

# The declared [SIM] process: the true log-odds of a drowning on a beach-day. Not the rules: steeper with high waves
# (two slopes), a current only matters above 1 km/h, a breeze only above 15 km/h.
_TRUE = {
    "intercept": -6.4,
    "waves_m": 1.2,
    "waves_over_1_5_m": 1.5,
    "current_over_1_kmh": 0.5,
    "onshore_over_15_kmh": 0.035,
    "heat_over_28_c": 0.07,
    "season": 1.1,
    "crowd_high": 0.6,
    "unguarded_in_season": 0.9,
    "past_drownings": 0.3,
}


def features(inputs: risk.DayInputs, rules: dict[str, Any]) -> list[float]:
    """The model's inputs; an unknown value takes a calm default (as the rules give it no points)."""
    waves = inputs.wave_height_m if inputs.wave_height_m is not None else 0.5
    season = inputs.day.month in rules["season_months"]
    heat = inputs.max_temperature_c if inputs.max_temperature_c is not None else 25.0
    return [
        waves,
        max(0.0, waves - 1.5),
        inputs.current_kmh if inputs.current_kmh is not None else 0.5,
        inputs.onshore_wind_kmh if inputs.onshore_wind_kmh is not None else 0.0,
        max(0.0, heat - 28.0),
        1.0 if season else 0.0,
        1.0 if inputs.crowd == "high" else 0.0,
        1.0 if season and inputs.guarded is False else 0.0,
        float(min(inputs.incidents, 5)),
    ]


def probability(params: dict[str, Any], inputs: risk.DayInputs, rules: dict[str, Any]) -> float:
    z = float(params["intercept"]) + sum(
        float(c) * x for c, x in zip(params["coef"], features(inputs, rules), strict=True)
    )
    return 1.0 / (1.0 + math.exp(-max(-60.0, min(60.0, z))))


def level(params: dict[str, Any], p: float) -> str:
    cutoffs = params["cutoffs"]
    if p >= float(cutoffs["red"]):
        return "red"
    if p >= float(cutoffs["yellow"]):
        return "yellow"
    return "green"


def simulate(n: int, seed: int, rules: dict[str, Any]) -> tuple[list[risk.DayInputs], list[int]]:
    """[SIM] beach-days and whether a drowning happened, from the declared process above."""
    rng = random.Random(seed)  # noqa: S311 (a reproducible simulation, not a secret)
    days: list[risk.DayInputs] = []
    labels: list[int] = []
    for _ in range(n):
        month = rng.choice((5, 6, 6, 7, 7, 7, 8, 8, 8, 9, 9, 10))
        waves = min(5.0, rng.lognormvariate(-0.4, 0.6))
        current = min(4.0, rng.lognormvariate(-0.5, 0.6))
        onshore = max(0.0, rng.gauss(14.0, 10.0))
        heat = rng.gauss(31.0 if month in (7, 8) else 27.0, 4.0)
        crowd = rng.choice(("high", "medium", "low", None))
        guarded = rng.random() < 0.6
        incidents = min(5, int(rng.expovariate(1.5)))
        inputs = risk.DayInputs(
            day=date(2026, month, 15),
            wave_height_m=round(waves, 2),
            current_kmh=round(current, 2),
            max_temperature_c=round(heat, 1),
            onshore_wind_kmh=round(onshore, 1),
            crowd=crowd,
            guarded=guarded,
            incidents=incidents,
        )
        season = month in rules["season_months"]
        z = (
            _TRUE["intercept"]
            + _TRUE["waves_m"] * waves
            + _TRUE["waves_over_1_5_m"] * max(0.0, waves - 1.5)
            + _TRUE["current_over_1_kmh"] * max(0.0, current - 1.0)
            + _TRUE["onshore_over_15_kmh"] * max(0.0, onshore - 15.0)
            + _TRUE["heat_over_28_c"] * max(0.0, heat - 28.0)
            + _TRUE["season"] * season
            + _TRUE["crowd_high"] * (crowd == "high")
            + _TRUE["unguarded_in_season"] * (season and not guarded)
            + _TRUE["past_drownings"] * incidents
        )
        days.append(inputs)
        labels.append(1 if rng.random() < 1.0 / (1.0 + math.exp(-z)) else 0)
    return days, labels


def _shares(levels: list[str]) -> dict[str, float]:
    return {name: round(sum(lv == name for lv in levels) / len(levels), 4) for name in risk.LEVELS}


def _caught(levels: list[str], labels: list[int]) -> dict[str, Any]:
    """Drowning days the levels flagged (yellow or red) or missed (green): the false negatives of the card."""
    positives = [lv for lv, y in zip(levels, labels, strict=True) if y]
    missed = sum(lv == "green" for lv in positives)
    return {
        "drowning_days": len(positives),
        "missed": missed,
        "missed_rate": round(missed / len(positives), 4) if positives else None,
        "red": sum(lv == "red" for lv in positives),
    }


def train(seed: int, rules: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fits the model on [SIM] days and measures it against the rules on other [SIM] days (another seed)."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score

    days, labels = simulate(TRAIN_DAYS, seed, rules)
    model = LogisticRegression(max_iter=2000)
    model.fit([features(d, rules) for d in days], labels)
    params: dict[str, Any] = {
        "features": list(FEATURES),
        "coef": [round(float(c), 6) for c in model.coef_[0]],
        "intercept": round(float(model.intercept_[0]), 6),
    }
    # Cut-offs: flag the same share of training days as the rules flag yellow-or-above and red.
    rule_levels = [risk.assess(d, rules).level for d in days]
    shares = _shares(rule_levels)
    ps = sorted((probability({**params, "cutoffs": {"yellow": 1, "red": 1}}, d, rules) for d in days), reverse=True)

    def cut(share: float) -> float:
        k = round(share * len(ps))
        return ps[k - 1] if k > 0 else 1.0

    params["cutoffs"] = {"yellow": round(cut(shares["yellow"] + shares["red"]), 6), "red": round(cut(shares["red"]), 6)}

    test_days, test_labels = simulate(TEST_DAYS, seed + 1, rules)
    model_p = [probability(params, d, rules) for d in test_days]
    rule_assessed = [risk.assess(d, rules) for d in test_days]
    model_levels = [level(params, p) for p in model_p]
    rule_test_levels = [r.level for r in rule_assessed]
    metrics = {
        "simulated": True,
        "train_days": TRAIN_DAYS,
        "test_days": TEST_DAYS,
        "drowning_rate": round(sum(test_labels) / TEST_DAYS, 4),
        "auc": {
            "model": round(float(roc_auc_score(test_labels, model_p)), 3),
            "rules": round(float(roc_auc_score(test_labels, [r.score for r in rule_assessed])), 3),
        },
        "flagged": {"model": _shares(model_levels), "rules": _shares(rule_test_levels)},
        "caught": {"model": _caught(model_levels, test_labels), "rules": _caught(rule_test_levels, test_labels)},
        "agreement": round(sum(a == b for a, b in zip(model_levels, rule_test_levels, strict=True)) / TEST_DAYS, 4),
    }
    return params, metrics


async def latest(session: AsyncSession) -> RiskModel | None:
    return await session.scalar(select(RiskModel).order_by(RiskModel.version.desc()).limit(1))


async def store(
    session: AsyncSession, seed: int, params: dict[str, Any], metrics: dict[str, Any], actor_name: str
) -> RiskModel:
    """Keeps a trained version; the next daily computation applies it in shadow."""
    version = int(await session.scalar(select(func.coalesce(func.max(RiskModel.version), 0))) or 0) + 1
    row = RiskModel(
        version=version,
        algorithm=ALGORITHM,
        params=params,
        metrics=metrics,
        simulated=True,
        seed=seed,
        trained_by_name=actor_name,
    )
    session.add(row)
    await session.flush()
    return row


def assess(model: RiskModel | None, inputs: risk.DayInputs, rules: dict[str, Any]) -> dict[str, Any]:
    """The shadow columns of a beach-day (all None without a trained model)."""
    if model is None:
        return {"shadow_p": None, "shadow_level": None, "shadow_version": None}
    p = probability(model.params, inputs, rules)
    return {"shadow_p": round(p, 5), "shadow_level": level(model.params, p), "shadow_version": model.version}


_RANK = {name: i for i, name in enumerate(risk.LEVELS)}


async def comparison(session: AsyncSession, since: date) -> dict[str, Any]:
    """Day by day, how the shadow's levels compare with the rules' on the computed beach-days."""
    rows = (
        await session.execute(
            select(BeachDay.day, BeachDay.level, BeachDay.shadow_level)
            .where(BeachDay.day >= since, BeachDay.shadow_level.is_not(None))
            .order_by(BeachDay.day)
        )
    ).all()
    days: dict[date, dict[str, int]] = {}
    for day, rule_level, shadow_level in rows:
        counts = days.setdefault(day, {"beaches": 0, "same": 0, "model_higher": 0, "model_lower": 0})
        counts["beaches"] += 1
        diff = _RANK[str(shadow_level)] - _RANK[rule_level]
        counts["same" if diff == 0 else "model_higher" if diff > 0 else "model_lower"] += 1
    total = {k: sum(c[k] for c in days.values()) for k in ("beaches", "same", "model_higher", "model_lower")}
    return {"days": [{"day": d.isoformat(), **c} for d, c in days.items()], "total": total}


async def _main(seed: int) -> None:
    from app.core.db import dispose_engine, get_system_sessionmaker
    from app.modules.audit import service as audit
    from app.modules.coastal import service

    try:
        async with get_system_sessionmaker()() as session:
            params, metrics = train(seed, await service.rules(session))
            row = await store(session, seed, params, metrics, audit.SYSTEM_ACTOR)
            await audit.record(
                session,
                actor=audit.SYSTEM_ACTOR,
                action="ai.model_trained",
                target=f"model:drowning:{row.version}",
                details={"seed": seed, "metrics": row.metrics},
            )
            await session.commit()
            print(f"drowning risk model v{row.version}: {row.metrics['auc']} · caught {row.metrics['caught']}")
    finally:
        await dispose_engine()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, default=7)
    asyncio.run(_main(parser.parse_args().seed))
