#!/bin/sh
# covers: NFR-12
# Restore drill (phase 10 §2.1, NFR-12: RPO < 5 min, RTO < 1 h). Self-contained: two throwaway clusters.
#
#   1. start a cluster with WAL archiving (infra/postgres/ehimaya-archive-wal);
#   2. migrate it (alembic, unless DRILL_MIGRATE=0) and write rows, audited;
#   3. take a base backup (infra/backup/backup.sh's options) and write more rows;
#   4. note the target time, write rows that must NOT come back, switch WAL and wait for the archive;
#   5. restore into a second cluster at the target time (infra/backup/restore.sh);
#   6. check that every row written before the target is back, none written after, and audit.verify_chain() is NULL;
#   7. print the restore time (RTO) and the archive lag (RPO).
#
# Needs the PostgreSQL server binaries (PG_BIN, default `pg_config --bindir`) with PostGIS and pgvector, and `uv`
# for the migrations. Run as root or as an ordinary user; as root, the clusters run as `postgres`.
set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
PG_BIN="${PG_BIN:-$(pg_config --bindir)}"
PORT_A="${DRILL_PORT_A:-55432}"
PORT_B="${DRILL_PORT_B:-55433}"
WORK=$(mktemp -d "${TMPDIR:-/tmp}/ehimaya-drill.XXXXXX")
ARCHIVE="$WORK/archive"
DATA_A="$WORK/primary"
DATA_B="$WORK/restored"

as_pg() {
  if [ "$(id -u)" = 0 ]; then runuser -u postgres -- "$@"; else "$@"; fi
}
psql_a() { "$PG_BIN/psql" -X -q -v ON_ERROR_STOP=1 -h 127.0.0.1 -p "$PORT_A" -U postgres -d ehimaya -tA "$@"; }
psql_b() { "$PG_BIN/psql" -X -q -v ON_ERROR_STOP=1 -h 127.0.0.1 -p "$PORT_B" -U postgres -d ehimaya -tA "$@"; }
step() { printf '\n== %s\n' "$*"; }
fail() { echo "DRILL FAILED: $*" >&2; exit 1; }

cleanup() {
  as_pg "$PG_BIN/pg_ctl" -D "$DATA_B" -m immediate stop >/dev/null 2>&1 || true
  as_pg "$PG_BIN/pg_ctl" -D "$DATA_A" -m immediate stop >/dev/null 2>&1 || true
  rm -rf "$WORK"
}
trap cleanup EXIT INT TERM

mkdir -p "$ARCHIVE/wal" "$ARCHIVE/base"
[ "$(id -u)" = 0 ] && chown -R postgres "$WORK"

step "1. primary cluster with WAL archiving"
as_pg "$PG_BIN/initdb" -D "$DATA_A" -U postgres --auth=trust -E UTF8 --locale=C.UTF-8 >/dev/null
cat >> "$DATA_A/postgresql.conf" <<CONF
listen_addresses = '127.0.0.1'
port = $PORT_A
unix_socket_directories = '$WORK'
wal_level = replica
archive_mode = on
archive_command = 'WAL_ARCHIVE_DIR=$ARCHIVE/wal $REPO/infra/postgres/ehimaya-archive-wal %p %f'
archive_timeout = 60
CONF
as_pg "$PG_BIN/pg_ctl" -D "$DATA_A" -l "$WORK/primary.log" -w start >/dev/null
"$PG_BIN/psql" -X -q -h 127.0.0.1 -p "$PORT_A" -U postgres -d postgres -c "CREATE DATABASE ehimaya"

step "2. schema and first rows"
if [ "${DRILL_MIGRATE:-1}" = 1 ]; then
  for ext in postgis vector pgcrypto pg_trgm; do psql_a -c "CREATE EXTENSION IF NOT EXISTS $ext"; done
  (cd "$REPO/services/api" && DATABASE_URL="postgresql+asyncpg://postgres@127.0.0.1:$PORT_A/ehimaya" \
    DB_RUNTIME_ROLE="" uv run --frozen alembic upgrade head >"$WORK/migrate.log" 2>&1) \
    || { cat "$WORK/migrate.log" >&2; fail "migrations"; }
  audit="INSERT INTO audit.log (actor, action, target, details) VALUES ('drill', 'drill.row', 'PHASE', '{}');"
else
  audit=""
fi
psql_a -c "CREATE SCHEMA drill; CREATE TABLE drill.row (id serial PRIMARY KEY, phase text NOT NULL,
           at timestamptz NOT NULL DEFAULT clock_timestamp())"
write_rows() {
  for i in 1 2 3 4 5; do
    psql_a -c "INSERT INTO drill.row (phase) VALUES ('$1'); $(echo "$audit" | sed "s/PHASE/$1/")"
  done
}
write_rows before_base

step "3. base backup, then more rows"
as_pg "$PG_BIN/pg_basebackup" -h 127.0.0.1 -p "$PORT_A" -U postgres -D "$ARCHIVE/base/drill" -F tar -z -X none \
  -c fast -l ehimaya-drill --manifest-checksums=SHA256
write_rows after_base

step "4. target time, rows after it, WAL archived"
TARGET=$(psql_a -c "SELECT clock_timestamp()")
sleep 1
write_rows after_target
marker_at=$(date +%s)
SEGMENT=$(psql_a -c "SELECT pg_walfile_name(pg_switch_wal())")
i=0
until [ -f "$ARCHIVE/wal/$SEGMENT" ]; do
  i=$((i + 1))
  [ "$i" -le 300 ] || fail "segment $SEGMENT not archived after 300 s"
  sleep 1
done
RPO=$(( $(date +%s) - marker_at ))
echo "target $TARGET, segment $SEGMENT archived"
as_pg "$PG_BIN/pg_ctl" -D "$DATA_A" -m fast stop >/dev/null

step "5. restore at the target time"
started=$(date +%s)
as_pg env PATH="$PG_BIN:$PATH" "$HERE/restore.sh" "$ARCHIVE/base/drill" "$DATA_B" --target-time "$TARGET" --wal-dir "$ARCHIVE/wal"
cat >> "$DATA_B/postgresql.auto.conf" <<CONF
port = $PORT_B
unix_socket_directories = '$WORK'
archive_mode = off
CONF
as_pg "$PG_BIN/pg_ctl" -D "$DATA_B" -l "$WORK/restored.log" -w -t 3600 start >/dev/null
i=0
until [ "$(psql_b -c 'SELECT pg_is_in_recovery()')" = f ]; do
  i=$((i + 1))
  [ "$i" -le 3600 ] || fail "still in recovery after an hour"
  sleep 1
done
RTO=$(( $(date +%s) - started ))

step "6. checks"
counts=$(psql_b -c "SELECT string_agg(phase || '=' || n, ' ' ORDER BY phase)
                    FROM (SELECT phase, count(*) AS n FROM drill.row GROUP BY phase) c")
echo "rows restored: $counts"
[ "$counts" = "after_base=5 before_base=5" ] || fail "expected after_base=5 before_base=5, got '$counts'"
if [ -n "$audit" ]; then
  broken=$(psql_b -c "SELECT audit.verify_chain()")
  [ -z "$broken" ] || fail "audit chain broken at seq $broken"
  echo "audit chain intact ($(psql_b -c "SELECT count(*) FROM audit.log WHERE actor = 'drill'") drill entries)"
fi

step "7. result"
echo "RTO (restore + replay + open): ${RTO} s (objective < 3600 s)"
echo "RPO (archive lag of the last segment): ${RPO} s (objective < 300 s)"
[ "$RTO" -lt 3600 ] || fail "RTO objective missed"
[ "$RPO" -lt 300 ] || fail "RPO objective missed"
echo "DRILL PASSED"
