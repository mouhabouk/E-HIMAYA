#!/bin/sh
# Nightly base backup of the e-Himaya cluster (phase 10 §2.1), run by the `backup` service of compose.prod.yml.
#
#   backup.sh once     one base backup now, then prune and write the metrics
#   backup.sh daemon   the same every night at BACKUP_HOUR (UTC, default 01), and the metrics every minute
#
# Environment: PGHOST, PGUSER, PGPASSWORD (a replication-capable role), ARCHIVE_DIR (default /archive),
# BACKUP_KEEP (daily backups kept, default 7), BACKUP_REMOTE (optional `rclone` remote:path, copied after each
# backup), METRICS_DIR (optional textfile collector directory).
set -eu

ARCHIVE_DIR="${ARCHIVE_DIR:-/archive}"
BASE_DIR="$ARCHIVE_DIR/base"
WAL_DIR="$ARCHIVE_DIR/wal"
KEEP="${BACKUP_KEEP:-7}"
HOUR="${BACKUP_HOUR:-01}"

log() { printf '%s backup: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

metrics() {
  [ -n "${METRICS_DIR:-}" ] || return 0
  mkdir -p "$METRICS_DIR"
  last_base=0
  newest=$(ls -1 "$BASE_DIR" 2>/dev/null | grep -v '^\.' | sort | tail -n 1 || true)
  if [ -n "$newest" ] && [ -f "$BASE_DIR/$newest/backup_manifest" ]; then
    last_base=$(stat -c %Y "$BASE_DIR/$newest/backup_manifest")
  fi
  last_wal=0
  wal=$(ls -1t "$WAL_DIR" 2>/dev/null | grep -v '^\.' | head -n 1 || true)
  if [ -n "$wal" ]; then
    last_wal=$(stat -c %Y "$WAL_DIR/$wal")
  fi
  tmp="$METRICS_DIR/.ehimaya_backup.prom.$$"
  {
    echo "# HELP ehimaya_backup_last_base_timestamp_seconds End of the newest complete base backup."
    echo "# TYPE ehimaya_backup_last_base_timestamp_seconds gauge"
    echo "ehimaya_backup_last_base_timestamp_seconds $last_base"
    echo "# HELP ehimaya_backup_last_wal_timestamp_seconds Time the newest WAL segment reached the archive."
    echo "# TYPE ehimaya_backup_last_wal_timestamp_seconds gauge"
    echo "ehimaya_backup_last_wal_timestamp_seconds $last_wal"
  } > "$tmp"
  mv "$tmp" "$METRICS_DIR/ehimaya_backup.prom"
}

prune() {
  # Keep the KEEP newest base backups, and the WAL needed by the oldest one kept.
  ls -1 "$BASE_DIR" | grep -v '^\.' | sort | head -n "-$KEEP" | while read -r old; do
    log "removing base backup $old"
    rm -rf "${BASE_DIR:?}/$old"
  done
  oldest=$(ls -1 "$BASE_DIR" | grep -v '^\.' | sort | head -n 1 || true)
  [ -n "$oldest" ] || return 0
  label=$(ls -1 "$WAL_DIR" | grep '\.backup$' | while read -r b; do
    if grep -q "LABEL: ehimaya-$oldest" "$WAL_DIR/$b"; then echo "$b"; fi
  done | head -n 1)
  if [ -n "$label" ]; then
    pg_archivecleanup "$WAL_DIR" "$label"
  fi
}

once() {
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  target="$BASE_DIR/$stamp"
  tmp="$BASE_DIR/.$stamp"
  mkdir -p "$BASE_DIR" "$WAL_DIR"
  log "base backup $stamp"
  # Tar, compressed, with a manifest (pg_verifybackup); WAL comes from the archive, not the stream.
  pg_basebackup -D "$tmp" -F tar -z -X none -c fast -l "ehimaya-$stamp" --manifest-checksums=SHA256
  mv "$tmp" "$target"
  log "base backup $stamp done ($(du -sh "$target" | cut -f1))"
  prune
  if [ -n "${BACKUP_REMOTE:-}" ]; then
    log "copying to $BACKUP_REMOTE"
    rclone copy "$ARCHIVE_DIR" "$BACKUP_REMOTE" --immutable
  fi
  metrics
}

case "${1:-daemon}" in
  once) once ;;
  metrics) metrics ;;
  daemon)
    log "daemon: base backup every night at ${HOUR}:00 UTC, keeping $KEEP"
    done_on=""
    while true; do
      today=$(date -u +%Y-%m-%d)
      if [ "$(date -u +%H)" = "$HOUR" ] && [ "$done_on" != "$today" ]; then
        if once; then done_on="$today"; else log "base backup failed, retrying in 10 minutes"; sleep 540; fi
      fi
      metrics
      sleep 60
    done
    ;;
  *) echo "usage: backup.sh once|daemon|metrics" >&2; exit 2 ;;
esac
