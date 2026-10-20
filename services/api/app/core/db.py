"""Async SQLAlchemy engine, sessions and the row-level security scope of every transaction.

Row-level security (phase 9 §9, migration ``0025_rls_policies``) is the second layer of the scope rules, after the
API's own checks (``core/access.py``). The policies read three transaction-local settings, which an ``after_begin``
listener sets at the start of **every** transaction of a session (a request may commit several times, and pooled
connections must never carry a scope from one transaction to the next):

* ``ehimaya.scope`` — ``none`` (default: no rows), ``public`` (a reporter: own rows), ``gouvernorat`` (regional
  staff), ``national`` (central staff) or ``system`` (worker loops, CLIs, internal hooks, public lookups);
* ``ehimaya.gouvernorat`` — the regional staff member's gouvernorat code (empty otherwise);
* ``ehimaya.subject`` — the principal's subject (reporter user id, staff subject for break-glass grants).

Where the scope comes from, first match wins:
1. the session's ``info["db_scope"]`` — :func:`get_system_sessionmaker` sets :data:`SYSTEM_SCOPE` there;
2. the :data:`db_scope` context variable, set per request by the authentication dependencies
   (``core.access.db_scope`` is this same variable);
3. nothing: ``none``, so an unscoped request reads nothing from a protected table (fail closed).

The owner role (migrations, tests) is not subject to the policies (``FORCE ROW LEVEL SECURITY`` is not used); the
runtime role is ``NOBYPASSRLS`` (``core/db_roles.py``), so every API and worker query goes through them.
"""

from collections.abc import AsyncIterator
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import Connection, MetaData, event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, SessionTransaction

from app.core.config import get_settings

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# ---------------------------------------------------------------- row-level security scope

ScopeKind = Literal["none", "public", "gouvernorat", "national", "system"]
SCOPE_KINDS: frozenset[str] = frozenset({"none", "public", "gouvernorat", "national", "system"})
_MAX_SUBJECT = 255


@dataclass(frozen=True, slots=True)
class DbScope:
    """What the database lets the current transaction see (mirrors the API's principal)."""

    kind: ScopeKind
    gouvernorat: int | None = None
    subject: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in SCOPE_KINDS:
            raise ValueError(f"invalid database scope: {self.kind!r}")
        if self.kind == "gouvernorat":
            if self.gouvernorat is None or not 1 <= self.gouvernorat <= 99:
                raise ValueError("a gouvernorat scope needs a gouvernorat code (1-99)")
        elif self.gouvernorat is not None:
            raise ValueError(f"a {self.kind} scope carries no gouvernorat")
        if self.kind == "public" and not self.subject:
            raise ValueError("a public scope needs the reporter's user id as subject")
        if self.subject is not None and (len(self.subject) > _MAX_SUBJECT or "\x00" in self.subject):
            raise ValueError("invalid database scope subject")

    @classmethod
    def public(cls, user_id: object) -> "DbScope":
        """A reporter (anonymous device or citizen account): their own reports, media and streams."""
        return cls("public", subject=str(user_id))

    @classmethod
    def staff(cls, *, gouvernorat_code: int | None, subject: str) -> "DbScope":
        """A staff principal: ``gouvernorat_code`` None = national scope."""
        if gouvernorat_code is None:
            return cls("national", subject=subject)
        return cls("gouvernorat", gouvernorat=gouvernorat_code, subject=subject)

    def settings(self) -> dict[str, str]:
        """Values of the ``ehimaya.*`` settings (empty string = unset)."""
        return {
            "scope": self.kind,
            "gouvernorat": "" if self.gouvernorat is None else str(self.gouvernorat),
            "subject": self.subject or "",
        }


NO_SCOPE = DbScope("none")
SYSTEM_SCOPE = DbScope("system")

#: Scope of the current request. Re-exported as ``core.access.db_scope``; the authentication dependencies set it (in
#: ``async def`` dependencies: a sync dependency runs in a copied context and its value would be lost).
db_scope: ContextVar[DbScope | None] = ContextVar("ehimaya_db_scope", default=None)

_INFO_KEY = "db_scope"
_SET_SCOPE = text(
    "SELECT set_config('ehimaya.scope', :scope, true), set_config('ehimaya.gouvernorat', :gouvernorat, true), "
    "set_config('ehimaya.subject', :subject, true)"
)


def current_scope(session: Session) -> DbScope:
    """The scope a new transaction of ``session`` runs with (see the module docstring for the order)."""
    pinned = session.info.get(_INFO_KEY)
    if isinstance(pinned, DbScope):
        return pinned
    scope = db_scope.get()
    if scope is None:
        scope = _access_scope()
    return scope if isinstance(scope, DbScope) else NO_SCOPE


def _access_scope() -> object:
    """``core.access.db_scope`` when it is a separate variable from :data:`db_scope` (it should be the same one)."""
    import sys

    module = sys.modules.get("app.core.access")
    var = getattr(module, "db_scope", None) if module is not None else None
    if isinstance(var, ContextVar) and var is not db_scope:
        return var.get(None)
    return None


class ScopedSession(Session):
    """Session class whose every transaction starts by setting the row-level security scope."""


@event.listens_for(ScopedSession, "after_begin")
def _apply_scope(session: Session, transaction: SessionTransaction, connection: Connection) -> None:
    connection.execute(_SET_SCOPE, current_scope(session).settings())


def make_sessionmaker(engine: AsyncEngine, *, scope: DbScope | None = None) -> async_sessionmaker[AsyncSession]:
    """Sessions on ``engine`` that set the scope per transaction; ``scope`` pins one (else the request's)."""
    info: dict[str, Any] = {_INFO_KEY: scope} if scope is not None else {}
    return async_sessionmaker(engine, expire_on_commit=False, sync_session_class=ScopedSession, info=info)


# ---------------------------------------------------------------- engine and sessions

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None
_system_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine, _sessionmaker, _system_sessionmaker
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_pre_ping=True,
        )
        _sessionmaker = make_sessionmaker(_engine)
        _system_sessionmaker = make_sessionmaker(_engine, scope=SYSTEM_SCOPE)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Sessions scoped by the current request (:data:`db_scope`); unscoped = no protected rows."""
    get_engine()
    assert _sessionmaker is not None
    return _sessionmaker


def get_system_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Sessions with the ``system`` scope (every row): worker loops, CLIs, internal hooks and the few public paths
    that look one row up by an unguessable key (``/reports/track``). Never for a request acting for a principal."""
    get_engine()
    assert _system_sessionmaker is not None
    return _system_sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        yield session


async def get_system_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency for internal hook routers (``system`` scope)."""
    async with get_system_sessionmaker()() as session:
        yield session


async def dispose_engine() -> None:
    global _engine, _sessionmaker, _system_sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None
    _system_sessionmaker = None
