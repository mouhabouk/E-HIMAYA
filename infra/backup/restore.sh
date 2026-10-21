#!/bin/sh
# Restore a base backup into an EMPTY data directory and replay the archived WAL (phase 10 §2.1).
#
#   restore.sh <base backup dir> <new data dir> [--target-time '2026-10-21 10:15:00+01'] [--wal-dir DIR]
#
# Then start PostgreSQL on <new data dir>: it replays the WAL up to the target (or to the end of the archive),
# promotes and opens. Check with `SELECT audit.verify_chain()` (NULL = intact) before pointing the services at it.
set -eu

usage() { echo "usage: restore.sh <base> <datadir> [--target-time TIME] [--wal-dir DIR]" >&2; exit 2; }
[ $# -ge 2 ] || usage
base="$1"
data="$2"
shift 2
target=""
wal_dir="${WAL_ARCHIVE_DIR:-/archive/wal}"
while [ $# -gt 0 ]; do
  case "$1" in
    --target-time) target="$2"; shift 2 ;;
    --wal-dir) wal_dir="$2"; shift 2 ;;
    *) usage ;;
  esac
done

[ -f "$base/base.tar.gz" ] || { echo "restore: $base/base.tar.gz not found" >&2; exit 1; }
if [ -d "$data" ] && [ -n "$(ls -A "$data")" ]; then
  echo "restore: $data is not empty; refusing to overwrite a data directory" >&2
  exit 1
fi
mkdir -p "$data"
chmod 700 "$data"
tar -xzf "$base/base.tar.gz" -C "$data"
if [ -f "$base/backup_manifest" ] && command -v pg_verifybackup >/dev/null; then
  # The manifest covers the extracted files; WAL is checked by the replay itself.
  pg_verifybackup -n -m "$base/backup_manifest" "$data"
fi
{
  echo "restore_command = 'cp \"$wal_dir/%f\" \"%p\"'"
  if [ -n "$target" ]; then
    echo "recovery_target_time = '$target'"
    echo "recovery_target_action = 'promote'"
  fi
} >> "$data/postgresql.auto.conf"
touch "$data/recovery.signal"
echo "restore: $data ready; start PostgreSQL on it to replay the WAL${target:+ up to $target}"
