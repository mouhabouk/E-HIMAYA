#!/bin/bash
# أدوار قاعدة بيانات المنظومة: المالك (الترحيلات) ودور التشغيل (DML فقط). السكربت متساوي القوة (idempotent).
# Database roles of the platform, applied by a superuser. Safe to run any number of times:
#   - at first start, from /docker-entrypoint-initdb.d/20-ehimaya.sh (local socket);
#   - at every `docker compose up`, by the one-shot `db-roles` service (PGHOST=postgres), which also upgrades
#     volumes created before the runtime role existed.
#
#   EHIMAYA_DB_USER          owner of the database and of every schema: runs the migrations (MIGRATION_DATABASE_URL)
#   EHIMAYA_DB_RUNTIME_USER  the API's login (DATABASE_URL): SELECT/INSERT/UPDATE/DELETE, and only SELECT/INSERT on
#                            audit.log. It owns nothing, so it can never ALTER, TRUNCATE or DISABLE TRIGGER.
# The table grants themselves are applied by the owner after every migration (services/api/migrations/grants.py),
# together with ALTER DEFAULT PRIVILEGES for the tables later migrations create.
set -euo pipefail

: "${EHIMAYA_DB_NAME:=ehimaya}"
: "${EHIMAYA_DB_USER:=ehimaya}"
: "${EHIMAYA_DB_RUNTIME_USER:=ehimaya_app}"
: "${EHIMAYA_DB_RUNTIME_PASSWORD:?set EHIMAYA_DB_RUNTIME_PASSWORD}"
: "${KEYCLOAK_DB_NAME:=keycloak}"
SUPERUSER="${POSTGRES_USER:-${PGUSER:-postgres}}"

if [ -n "${PGHOST:-}" ]; then
  # Over the network the server may still be running its first-start scripts (socket only): wait for TCP.
  for _ in $(seq 1 60); do
    pg_isready -q -h "$PGHOST" -U "$SUPERUSER" -d postgres && break
    sleep 2
  done
fi

psql -v ON_ERROR_STOP=1 --username "$SUPERUSER" --dbname postgres \
  -v app_user="$EHIMAYA_DB_USER" -v app_db="$EHIMAYA_DB_NAME" -v kc_db="$KEYCLOAK_DB_NAME" \
  -v rt_user="$EHIMAYA_DB_RUNTIME_USER" -v rt_pass="$EHIMAYA_DB_RUNTIME_PASSWORD" <<-'EOSQL'
	SELECT format('CREATE ROLE %I LOGIN', :'rt_user')
	 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'rt_user') \gexec
	ALTER ROLE :"rt_user" WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
	  PASSWORD :'rt_pass';
	-- The owner may SET ROLE to the runtime role (privilege checks, tests) without inheriting anything from it.
	GRANT :"rt_user" TO :"app_user" WITH INHERIT FALSE, SET TRUE;
	-- Only the two roles may connect to the application database; Keycloak's database is its owner's alone.
	REVOKE ALL ON DATABASE :"app_db" FROM PUBLIC;
	GRANT CONNECT ON DATABASE :"app_db" TO :"rt_user";
	REVOKE ALL ON DATABASE :"kc_db" FROM PUBLIC;
EOSQL

# PostgreSQL 15+ already denies CREATE on public to PUBLIC; make it explicit for upgraded clusters.
psql -v ON_ERROR_STOP=1 --username "$SUPERUSER" --dbname "$EHIMAYA_DB_NAME" <<-'EOSQL'
	REVOKE CREATE ON SCHEMA public FROM PUBLIC;
EOSQL
echo "ehimaya-roles: runtime role ${EHIMAYA_DB_RUNTIME_USER} ready"
