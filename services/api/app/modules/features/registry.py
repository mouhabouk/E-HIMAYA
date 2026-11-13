"""The catalogue bound to the API routes (L4 §8): which feature guards a route, and who holds a feature by default.

Built once from the application's routes (``install``, called by ``app.main``). The roles of a feature are read from
the ``require_roles`` dependencies of its routes, so they follow the code; checks made inside a handler (the scope of
a gouvernorat, the access matrix) still apply on top.
"""

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi.routing import APIRoute, iter_route_contexts

from app.core.security import Role
from app.modules.features.catalogue import CATALOGUE, Kind, Names, Spec

STAFF_PREFIX = "/api/v1/staff"
# Phase 5 (Yamen 2026-11-01): the administrator also sets the windows and buttons of the field app (``/api/v1/crew``)
# and of the citizen app and the portal (the public API). Their routes enter the catalogue under a marker no
# dashboard path can take: ``/@crew/missions/...``, ``/@public/orgs/...``.
CREW_PREFIX = "/api/v1/crew"
CREW = "/@crew"
PUBLIC = "/@public"
# Public routes that stay out of the catalogue: the app's own plumbing, and what the platform never hides.
_PUBLIC_SKIP = (
    "/api/v1/app/",
    "/api/v1/geo/",
    "/api/v1/basemap/",
    "/api/v1/field/",
    # The inspector's app (phase I): its own accounts, activated by the inspector general, not a citizen's app.
    "/api/v1/inspect/",
    "/api/v1/verify/om/",
    "/api/v1/admin/",
    # The camera bridges: machines signing with their camera's key, no person to grant or deny a button.
    "/api/v1/camera-events",
)
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
TECHNICAL = frozenset({Role.SYSADMIN, Role.SECURITY_ADMIN, Role.AI_ADMIN, Role.REGIONAL_ACCOUNT_ADMIN})
# Least privileged first: the role a grantee acts as when the catalogue does not name one.
_PREFERENCE = (
    Role.OPERATOR,
    Role.CONTENT_EDITOR,
    Role.ORG_AUDITOR,
    Role.MEDICAL_COORDINATOR,
    Role.PERSONNEL_OFFICER,
    Role.INSPECTOR_GENERAL,
    Role.MAINTENANCE_OFFICER,
    Role.FIELD_COMMANDER,
    Role.OPS_MANAGER,
    Role.LOCAL_COMMITTEE,
    Role.CENTRAL_COMMITTEE,
    Role.GOVERNOR,
    Role.MINISTER,
)


# The menu's one source (apps/dashboard/src/menu/menu.json, copied here by scripts/menu/sync.py): 20 systems in 4
# blocks (Yamen 2026-11-13). The administrator hides, suspends or grants a whole system at once.
MENU_FILE = Path(__file__).with_name("menu.json")
# A system's feature key: ``system.<key>`` (the key pattern of access.feature_rule; no page is called «system»).
SYSTEM_PREFIX = "system."


@dataclass(frozen=True)
class System:
    key: str
    number: int
    block: str
    names: Names
    # The dashboard paths of its entries (aliases left out, planned entries kept).
    paths: tuple[str, ...]
    planned: tuple[str, ...]


def load_menu(path: Path = MENU_FILE) -> dict[str, Any]:
    menu: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return menu


def menu_systems(menu: dict[str, Any] | None = None) -> tuple[System, ...]:
    menu = menu or load_menu()
    out = []
    for block in menu["blocks"]:
        for s in block["systems"]:
            names = s["names"]
            own = [i for i in s["items"] if not i.get("alias")]
            out.append(
                System(
                    key=s["key"],
                    number=s["number"],
                    block=block["key"],
                    names=(names["ar"], names["fr"], names["en"]),
                    paths=tuple(i["path"] for i in own if not i.get("planned")),
                    planned=tuple(i["path"] for i in own if i.get("planned")),
                )
            )
    return tuple(out)


def system_of_nav(systems: Sequence[System], nav: str | None) -> str | None:
    """The system of a dashboard path: the one listing it, else the one listing the longest path above it."""
    if not nav or nav == "/":
        return None
    best: tuple[int, str] | None = None
    for s in systems:
        for p in s.paths:
            if (nav == p or nav.startswith(p.rstrip("/") + "/")) and (best is None or len(p) > best[0]):
                best = (len(p), s.key)
    return best[1] if best else None


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
    # The menu system it belongs to (``system.<key>`` is its feature), None outside the dashboard menu.
    system: str | None = None


@dataclass(frozen=True)
class Registry:
    features: dict[str, Feature]
    order: tuple[str, ...]
    exact: dict[tuple[str, str], str]
    # (method rule, prefix, page key), longest prefix first.
    prefixes: tuple[tuple[str, str, str], ...]
    # Every route of the catalogue's surfaces: (method, path relative to the staff prefix or under a marker).
    routes: tuple[tuple[str, str], ...]
    systems: tuple[System, ...] = ()

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
        """The features guarding a route, most specific first (button or tab, then its page, then its system)."""
        key = self.owner(method, path)
        return self.chain(key) if key is not None else []

    def chain(self, key: str) -> list[Feature]:
        """A feature, its page, and the system of the most specific of them that has one."""
        chain: list[Feature] = []
        k: str | None = key
        while k is not None:
            feature = self.features[k]
            chain.append(feature)
            k = feature.parent
        system = next((f.system for f in chain if f.system), None)
        if system is not None and chain[0].kind != "system":
            chain.append(self.features[SYSTEM_PREFIX + system])
        return chain

    def system_pages(self, system: str) -> list[Feature]:
        """The pages of a system, and the tabs of other pages that show in its menu."""
        return [f for f in self.features.values() if f.kind in ("page", "tab") and f.system == system]


def _method_ok(rule: str, method: str) -> bool:
    return rule == "*" or rule == method or (rule == "WRITE" and method in WRITE_METHODS)


def _under(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + "/")


def relative(path: str) -> str | None:
    """The catalogue path of an API route: relative to the staff prefix, or under a surface marker; None if none."""
    if path.startswith(STAFF_PREFIX + "/"):
        return path[len(STAFF_PREFIX) :]
    if path.startswith(CREW_PREFIX + "/"):
        return CREW + path[len(CREW_PREFIX) :]
    if path.startswith("/api/v1/") and not path.startswith(_PUBLIC_SKIP):
        return PUBLIC + path[len("/api/v1") :]
    return None


def is_staff_path(path: str) -> bool:
    return not path.startswith((CREW + "/", PUBLIC + "/"))


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
        if not isinstance(route, APIRoute):
            continue
        path = relative(route.path)
        if path is not None:
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
    systems = menu_systems()
    registry = Registry({}, tuple(s.key for s, _ in specs), exact, tuple(prefixes), tuple(route_roles), systems)

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
            # A tab shown in the menu of another system belongs there (the locations to verify, under the GIS).
            system=system_of_nav(systems, spec.nav) or (system_of_nav(systems, parent.nav) if parent else None),
        )
    for s in systems:
        registry.features[SYSTEM_PREFIX + s.key] = Feature(
            key=SYSTEM_PREFIX + s.key,
            kind="system",
            names=s.names,
            page=SYSTEM_PREFIX + s.key,
            parent=None,
            flags=frozenset(),
            nav=None,
            group=s.key,
            roles=frozenset(),
            act_as=None,
            routes=(),
            system=s.key,
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
