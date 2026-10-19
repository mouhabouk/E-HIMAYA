import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.core.db import Base
from app.core.db_roles import apply_runtime_grants
from app.modules import models  # noqa: F401  (registers all tables on Base.metadata)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
# Migrations run as the owner of the database (MIGRATION_DATABASE_URL); the API itself connects with the runtime
# role (DATABASE_URL), which owns nothing. Single-role development setups leave MIGRATION_DATABASE_URL unset.
MIGRATION_URL = os.environ.get("MIGRATION_DATABASE_URL") or get_settings().database_url
# Runtime role granted DML on the migrated schemas after every upgrade (app/core/db_roles.py). Empty = no grants.
RUNTIME_ROLE = os.environ.get("DB_RUNTIME_ROLE", "").strip()
config.set_main_option("sqlalchemy.url", MIGRATION_URL.replace("%", "%%"))
target_metadata = Base.metadata

SCHEMAS = ("geo", "identity", "reports", "ops", "audit")


def include_name(name: str | None, type_: str, parent_names: dict[str, str | None]) -> bool:
    if type_ == "schema":
        return name in SCHEMAS
    return True


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        include_name=include_name,
        version_table_schema="public",
        transaction_per_migration=True,
    )
    with context.begin_transaction():
        context.run_migrations()
    if RUNTIME_ROLE:
        schemas = apply_runtime_grants(connection, RUNTIME_ROLE)
        connection.commit()
        print(f"runtime grants for {RUNTIME_ROLE}: {', '.join(schemas) or 'role absent, skipped'}")


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(run_async_migrations())
