"""Grants and hidings of the administrator (L4 §8): the rules in force, what they mean for a principal, the ceiling.

Precedence, for each feature of a route's chain (button or tab, then its page): the account's own rules, else the
rules of its roles (in every gouvernorat or in its own); a hiding wins over a grant at the same level. A hidden page
hides everything under it. A grant lets the account act as the feature's ``act_as`` role on that route only, never
on a write route through a page grant, and never beyond the fixed ceiling (``ceiling``).
"""

import time
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Literal

import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_system_sessionmaker
from app.core.security import Principal, Realm, Role
from app.modules.features import registry
from app.modules.features.models import FeatureRule
from app.modules.features.registry import TECHNICAL, WRITE_METHODS, Feature

log = structlog.get_logger()

State = Literal["grant", "hide", "suspend"] | None
FEATURE_HIDDEN = "feature_hidden"
# The page the administrator works from: never hidden from a national system administrator (no lock-out).
PERMISSIONS = "permissions"
# The pages the national system administrator always keeps, whatever hides their page or their system (2026-11-13).
ADMIN_KEEPS = frozenset({PERMISSIONS, "systems"})
# Never granted a feature showing personal data (reporters, callers, victims, citizens, personnel).
NO_PERSONAL = frozenset({Role.GOVERNOR, Role.MINISTER})


@dataclass(frozen=True, slots=True)
class Rule:
    id: uuid.UUID
    feature_key: str
    # «suspend» (2026-11-13): a whole system closed for a while; it hides like «hide» and shows ``message``.
    effect: Literal["grant", "hide", "suspend"]
    target_kind: Literal["user", "role", "everyone"]
    target: str
    gouvernorat_code: int | None
    starts_at: datetime | None
    ends_at: datetime | None
    message: dict[str, str] | None = None

    def active(self, now: datetime) -> bool:
        return (self.starts_at is None or self.starts_at <= now) and (self.ends_at is None or now < self.ends_at)


def _rule(row: FeatureRule) -> Rule:
    return Rule(
        row.id,
        row.feature_key,
        row.effect,  # type: ignore[arg-type]
        row.target_kind,  # type: ignore[arg-type]
        row.target,
        row.gouvernorat_code,
        row.starts_at,
        row.ends_at,
        row.message,
    )


# ---------------------------------------------------------------- the rules in force, cached per process

_TTL_S = 5.0
_cache: tuple[float, tuple[Rule, ...]] | None = None


def invalidate() -> None:
    global _cache
    _cache = None


async def load(session: AsyncSession, now: datetime) -> tuple[Rule, ...]:
    rows = await session.scalars(
        select(FeatureRule).where(
            FeatureRule.revoked_at.is_(None), or_(FeatureRule.ends_at.is_(None), FeatureRule.ends_at > now)
        )
    )
    return tuple(_rule(r) for r in rows)


async def rules_in_force() -> tuple[Rule, ...]:
    """Rules not revoked nor ended (the start is checked per request); read at most every few seconds."""
    global _cache
    if _cache is not None and time.monotonic() - _cache[0] < _TTL_S:
        return _cache[1]
    async with get_system_sessionmaker()() as session:
        rules = await load(session, datetime.now(UTC))
    _cache = (time.monotonic(), rules)
    return rules


# ---------------------------------------------------------------- deciding


def _admin(principal: Principal) -> bool:
    return principal.is_national and Role.SYSADMIN in principal.roles


def _applying(principal: Principal, key: str, rules: Iterable[Rule], now: datetime) -> list[Rule]:
    """The rules of ``key`` that reach ``principal``: the account's own if any, else those of its roles."""
    mine: list[Rule] = []
    of_roles: list[Rule] = []
    for r in rules:
        if r.feature_key != key or not r.active(now):
            continue
        if r.target_kind == "user" and r.target == principal.subject:
            mine.append(r)
        elif (
            r.target_kind == "role"
            and r.target in principal.roles
            and (r.gouvernorat_code is None or r.gouvernorat_code == principal.gouvernorat_code)
        ) or r.target_kind == "everyone":
            # A rule for everyone (phase 5: a window closed for all the users of a surface) counts as a role rule.
            of_roles.append(r)
    return mine or of_roles


def state(principal: Principal, feature: Feature, rules: Iterable[Rule], now: datetime) -> State:
    level = {r.effect for r in _applying(principal, feature.key, rules, now)}
    if "hide" in level:
        return "hide"
    if "suspend" in level:
        return "suspend"
    return "grant" if level else None


def suspension(principal: Principal, system_key: str, rules: Iterable[Rule], now: datetime) -> dict[str, str] | None:
    """The administrator's message when the system is suspended for ``principal`` (and not hidden), else None."""
    applying = _applying(principal, registry.SYSTEM_PREFIX + system_key, rules, now)
    if any(r.effect == "hide" for r in applying):
        return None
    found = next((r for r in applying if r.effect == "suspend"), None)
    if found is None:
        return None
    return found.message or {"ar": "", "fr": "", "en": ""}


def ceiling(principal: Principal, feature: Feature) -> str | None:
    """Why a grant of ``feature`` cannot reach ``principal`` (the fixed security rules), or None."""
    if feature.act_as is None or "fixed" in feature.flags:
        return "fixed"
    if not principal.is_staff:
        return "not_staff"
    if principal.roles & TECHNICAL:
        # Technical accounts never receive operational rights (phase 9 §1).
        return "technical_account"
    if "personal" in feature.flags and principal.roles & NO_PERSONAL:
        return "personal_data"
    if "national" in feature.flags and not principal.is_national:
        return "national_scope"
    return None


def holds_by_default(principal: Principal, feature: Feature) -> bool:
    if dormant(feature):
        return False
    return not feature.roles or bool(principal.roles & feature.roles)


def dormant(feature: Feature) -> bool:
    """Held by nobody until granted (the dry run, L5a); a safety button is never dormant."""
    return "dormant" in feature.flags and "safety" not in feature.flags


@dataclass(frozen=True, slots=True)
class Outcome:
    hidden: bool
    # The feature whose grant applies to this route, if any.
    granted: Feature | None


def decide(
    principal: Principal, chain: Sequence[Feature], method: str, rules: Iterable[Rule], now: datetime
) -> Outcome:
    rules = tuple(rules)
    if chain and "safety" in chain[0].flags:
        # Never hidden nor dormant: the handler checks who may press it (the stop of a dry run).
        return Outcome(False, None)
    granted: Feature | None = None
    for feature in chain:
        st = state(principal, feature, rules, now)
        if st in ("hide", "suspend"):
            if chain[0].page in ADMIN_KEEPS and _admin(principal):
                continue
            return Outcome(True, None)
        if st == "grant" and granted is None and ceiling(principal, feature) is None:
            # A page grant opens its pages' reads; a write needs the grant of its button.
            if feature.kind != "page" or method not in WRITE_METHODS:
                granted = feature
    if granted is None and any(dormant(f) for f in chain):
        return Outcome(True, None)
    return Outcome(False, granted)


def elevate(principal: Principal, feature: Feature) -> Principal:
    assert feature.act_as is not None
    if feature.act_as in principal.roles:
        return principal
    return replace(principal, roles=principal.roles | {feature.act_as})


async def apply(principal: Principal, method: str, route_path: str | None) -> Principal:
    """Refuse a hidden route (403 feature_hidden) and lend the granted role on a granted one."""
    path = registry.relative(route_path) if route_path is not None else None
    if not principal.is_staff or path is None:
        return principal
    chain = registry.get().match(method, path)
    if not chain:
        return principal
    rules = await rules_in_force()
    if not rules and not any(dormant(f) for f in chain):
        return principal
    outcome = decide(principal, chain, method, rules, datetime.now(UTC))
    if outcome.hidden:
        from fastapi import HTTPException, status

        log.info("feature_hidden", feature=chain[0].key)
        raise HTTPException(status.HTTP_403_FORBIDDEN, FEATURE_HIDDEN)
    if outcome.granted is not None:
        return elevate(principal, outcome.granted)
    return principal


def _hidden_for(principal: Principal | None, chain: Sequence[Feature], method: str, rules: Iterable[Rule]) -> bool:
    if principal is None:
        rules = [r for r in rules if r.target_kind == "everyone"]
        return decide(Principal("", Realm.PUBLIC, frozenset()), chain, method, rules, datetime.now(UTC)).hidden
    return decide(principal, chain, method, rules, datetime.now(UTC)).hidden


async def guard(principal: Principal | None, method: str, route_path: str | None) -> None:
    """The citizen app and the portal (phase 5): a window the administrator closed answers 403 feature_hidden, to an
    anonymous caller too. Staff callers are decided by ``apply`` (their roles, the grants)."""
    if principal is not None and principal.is_staff:
        return
    path = registry.relative(route_path) if route_path is not None else None
    if path is None or registry.is_staff_path(path):
        return
    chain = registry.get().match(method, path)
    if not chain:
        return
    rules = await rules_in_force()
    if not rules:
        return
    if _hidden_for(principal, chain, method, rules):
        from fastapi import HTTPException, status

        log.info("feature_hidden", feature=chain[0].key)
        raise HTTPException(status.HTTP_403_FORBIDDEN, FEATURE_HIDDEN)


async def hidden_keys(principal: Principal | None, surfaces: Iterable[str]) -> list[str]:
    """The features of the given groups hidden from the caller (the apps and the portal hide their windows)."""
    reg = registry.get()
    rules = await rules_in_force()
    groups = set(surfaces)
    out: list[str] = []
    for key in reg.order:
        f = reg.features[key]
        if f.group not in groups:
            continue
        chain = reg.chain(key)
        method = "POST" if f.kind == "button" else "GET"
        if principal is not None and principal.is_staff:
            hidden = decide(principal, chain, method, rules, datetime.now(UTC)).hidden
        else:
            hidden = _hidden_for(principal, chain, method, rules)
        if hidden:
            out.append(key)
    return out


@dataclass(frozen=True, slots=True)
class Effective:
    # Held through the account's roles (the routes' role checks; scope checks inside handlers still apply).
    default: bool
    hidden: bool
    # Granted by a rule that passes the ceiling; ``refused`` names the ceiling a grant rule hits.
    granted: bool
    refused: str | None

    @property
    def open(self) -> bool:
        return not self.hidden and (self.default or self.granted)


def effective(principal: Principal, rules: Iterable[Rule], now: datetime) -> dict[str, Effective]:
    """Every feature as it stands for ``principal``: for the dashboard's menu and buttons, and the preview."""
    rules = tuple(rules)
    reg = registry.get()
    out: dict[str, Effective] = {}
    for key in reg.order:
        f = reg.features[key]
        chain = reg.chain(key)
        hidden = decide(principal, chain, "POST" if f.kind == "button" else "GET", rules, now).hidden
        granted = state(principal, f, rules, now) == "grant"
        refused = ceiling(principal, f) if granted else None
        out[key] = Effective(holds_by_default(principal, f), hidden, granted and refused is None, refused)
    return out


async def granted(principal: Principal, key: str) -> bool:
    """A rule in force grants feature ``key`` (or its page, or its system) to ``principal``, within the ceiling.

    For the routes the administrator keeps by default and may lend (the inspections' bin, Yamen 2026-11-13)."""
    if not principal.is_staff:
        return False
    rules = await rules_in_force()
    if not rules:
        return False
    chain = registry.get().chain(key)
    outcome = decide(principal, chain, "POST" if chain[0].kind == "button" else "GET", rules, datetime.now(UTC))
    return not outcome.hidden and outcome.granted is not None


async def as_for(principal: Principal, key: str) -> Principal | None:
    """The principal as the routes of feature ``key`` see it: None when hidden, with the lent role when granted.

    For the ``can_*`` flags an answer computes for its buttons, so a granted button shows and a hidden one does not."""
    if not principal.is_staff:
        return principal
    reg = registry.get()
    chain = reg.chain(key)
    rules = await rules_in_force()
    if not rules and not any(dormant(f) for f in chain):
        return principal
    outcome = decide(principal, chain, "POST" if chain[0].kind == "button" else "GET", rules, datetime.now(UTC))
    if outcome.hidden:
        return None
    return elevate(principal, outcome.granted) if outcome.granted is not None else principal
