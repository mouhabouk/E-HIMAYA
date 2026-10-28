"""The catalogue bound to the API routes (L4 §8): which feature guards a route, and who holds a feature by default.

Built once from the application's routes (``install``, called by ``app.main``). The roles of a feature are read from
the ``require_roles`` dependencies of its routes, so they follow the code; checks made inside a handler (the scope of
a gouvernorat, the access matrix) still apply on top.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from fastapi.routing import APIRoute, iter_route_contexts

from app.core.security import Role
from app.modules.features.catalogue import CATALOGUE, Kind, Names, Spec

STAFF_PREFIX = "/api/v1/staff"
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
TECHNICAL = frozenset({Role.SYSADMIN, Role.SECURITY_ADMIN, Role.AI_ADMIN, Role.REGIONAL_ACCOUNT_ADMIN})
# Least privileged first: the role a grantee acts as when the catalogue does not name one.
_PREFERENCE = (
    Role.OPERATOR,
    Role.CONTENT_EDITOR,
    Role.ORG_AUDITOR,
    Role.MEDICAL_COORDINATOR,
    Role.FIELD_COMMANDER,
    Role.OPS_MANAGER,
    Role.LOCAL_COMMITTEE,
    Role.CENTRAL_COMMITTEE,
    Role.GOVERNOR,
    Role.MINISTER,
)


@dataclass(frozen=True)
class Feature:
    key: str
    kind: Kind
    names: Names
    page: str
    parent: str | None
    flags: frozenset[str]
    nav: str | None
    group: str | None
    # Who holds it by default (empty: any staff member); the role a grantee acts as (None: not grantable).
    roles: frozenset[Role]
    act_as: Role | None
    routes: tuple[str, ...]


@dataclass(frozen=True)
class Registry:
    features: dict[str, Feature]
    order: tuple[str, ...]
    exact: dict[tuple[str, str], str]
    # (method rule, prefix, page key), longest prefix first.
    prefixes: tuple[tuple[str, str, str], ...]
    # Every staff route: (method, path relative to the staff prefix).
    routes: tuple[tuple[str, str], ...]

    def owner(self, method: str, path: str) -> str | None:
        """The key of the most specific feature guarding a route."""
        method = "GET" if method == "HEAD" else method
        key = self.exact.get((method, path))
        if key is None:
            key = next(
                (k for rule, prefix, k in self.prefixes if _method_ok(rule, method) and _under(path, prefix)), None
            )
        return key

    def match(self, method: str, path: str) -> list[Feature]:
        """The features guarding a route, most specific first (button or tab, then its page); empty if none."""
        key = self.owner(method, path)
        chain: list[Feature] = []
        while key is not None:
            feature = self.features[key]
            chain.append(feature)
            key = feature.parent
        return chain


def _method_ok(rule: str, method: str) -> bool:
    return rule == "*" or rule == method or (rule == "WRITE" and method in WRITE_METHODS)


def _under(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + "/")


def _split(route: str) -> tuple[str, str]:
    method, _, path = route.partition(" ")
    return method, path


def _required_roles(dependant: Any) -> frozenset[Role] | None:
    """The roles a route's ``require_roles`` dependencies ask for (None when it has none)."""
    found: frozenset[Role] | None = None
    stack = list(dependant.dependencies)
    while stack:
        dep = stack.pop()
        roles = getattr(dep.call, "roles", None)
        if roles is not None:
            found = frozenset(roles) if found is None else found & frozenset(roles)
        stack.extend(dep.dependencies)
    return found


def _act_as(spec: Spec, flags: frozenset[str], roles: Sequence[frozenset[Role]]) -> Role | None:
    if "fixed" in flags:
        return None
    if spec.act_as is not None:
        return spec.act_as
    common = frozenset.intersection(*roles) if roles else frozenset()
    return next((r for r in _PREFERENCE if r in common), None)


def build(api_routes: Iterable[Any]) -> Registry:
    route_roles: dict[tuple[str, str], frozenset[Role] | None] = {}
    for context in iter_route_contexts(list(api_routes)):
        route = context.original_route
        if isinstance(route, APIRoute) and route.path.startswith(STAFF_PREFIX + "/"):
            path = route.path[len(STAFF_PREFIX) :]
            for method in route.methods or ():
                if method != "HEAD":
                    route_roles[(method, path)] = _required_roles(route.dependant)

    exact: dict[tuple[str, str], str] = {}
    prefixes: list[tuple[str, str, str]] = []
    specs: list[tuple[Spec, Spec | None]] = []
    for top in CATALOGUE:
        specs.append((top, None))
        specs.extend((child, top) for child in top.children)
        for rule, prefix in map(_split, top.routes):
            prefixes.append((rule, prefix, top.key))
        for child in top.children:
            for spec_route in child.routes:
                exact[_split(spec_route)] = child.key
    prefixes.sort(key=lambda p: -len(p[1]))
    registry = Registry({}, tuple(s.key for s, _ in specs), exact, tuple(prefixes), tuple(route_roles))

    owned: dict[str, list[frozenset[Role] | None]] = {}
    for method, path in route_roles:
        owner = registry.owner(method, path)
        if owner is not None:
            owned.setdefault(owner, []).append(route_roles[(method, path)])

    for spec, parent in specs:
        flags = spec.flags | (parent.flags if parent else frozenset())
        required = [r for r in owned.get(spec.key, []) if r is not None]
        roles = frozenset().union(*required) if required else frozenset()
        if parent is None:
            # A page is held by whoever holds one of its tabs or buttons too.
            for child in spec.children:
                roles |= frozenset().union(*[r for r in owned.get(child.key, []) if r is not None])
        registry.features[spec.key] = Feature(
            key=spec.key,
            kind=spec.kind,
            names=spec.names,
            page=parent.key if parent else spec.key,
            parent=parent.key if parent else None,
            flags=flags,
            nav=spec.nav,
            group=spec.group or (parent.group if parent else None),
            roles=roles,
            act_as=_act_as(spec, flags, required),
            routes=spec.routes,
        )
    return registry


_registry: Registry | None = None


def install(api_routes: Iterable[Any]) -> Registry:
    global _registry
    _registry = build(api_routes)
    return _registry


def get() -> Registry:
    if _registry is None:
        raise RuntimeError("features registry not installed")
    return _registry
