#!/bin/sh
# يشغّل الخدمة. الترحيلات تُطبَّق بخدمة منفصلة (migrate) بحساب مالك القاعدة، لا عند كل تشغيل.
# Migrations run in the one-shot `migrate` service as the database owner (MIGRATION_DATABASE_URL); the API runs
# with the runtime role, which cannot change the schema. RUN_MIGRATIONS=1 restores the single-container behaviour
# (development without compose).
set -e
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  alembic upgrade head
fi
exec "$@"
