#!/bin/bash
# ينشئ قاعدتي المنظومة و Keycloak بمستخدمين منفصلين.
# Creates the application and Keycloak databases with separate owners.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
  -v app_user="$EHIMAYA_DB_USER" -v app_pass="$EHIMAYA_DB_PASSWORD" -v app_db="$EHIMAYA_DB_NAME" \
  -v kc_user="$KEYCLOAK_DB_USER" -v kc_pass="$KEYCLOAK_DB_PASSWORD" -v kc_db="$KEYCLOAK_DB_NAME" <<-'EOSQL'
	CREATE ROLE :"app_user" LOGIN PASSWORD :'app_pass';
	CREATE DATABASE :"app_db" OWNER :"app_user" ENCODING 'UTF8' TEMPLATE template0;
	CREATE ROLE :"kc_user" LOGIN PASSWORD :'kc_pass';
	CREATE DATABASE :"kc_db" OWNER :"kc_user" ENCODING 'UTF8' TEMPLATE template0;
EOSQL

# Extensions need superuser; create them once so migrations can rely on them.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$EHIMAYA_DB_NAME" <<-'EOSQL'
	CREATE EXTENSION IF NOT EXISTS postgis;
	CREATE EXTENSION IF NOT EXISTS vector;
	CREATE EXTENSION IF NOT EXISTS pgcrypto;
EOSQL
