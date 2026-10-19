#!/bin/sh
# يطبّق ترحيلات قاعدة البيانات ثم يشغّل الخدمة.
set -e
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  alembic upgrade head
fi
exec "$@"
