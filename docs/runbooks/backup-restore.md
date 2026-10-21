# Backup and restore

Phase 10, contract §2.1. Objectives (NFR-12): lose at most 5 minutes of data (RPO), be back within 1 hour (RTO).

## What runs

| Piece | Where | What it does |
|---|---|---|
| WAL archiving | `postgres` service, `infra/postgres/ehimaya-archive-wal` | Copies each WAL segment to `/archive/wal` (volume `pgarchive`) as soon as it is full, and at least every 60 s |
| Base backup | `backup` service, `infra/backup/backup.sh daemon` | One `pg_basebackup` each night at `BACKUP_HOUR` (UTC) into `/archive/base/<date>`; keeps `BACKUP_KEEP` (7) and the WAL the oldest one needs |
| Second site | `BACKUP_REMOTE` (rclone `remote:path`) | Copied after each base backup. Off by default; the target must be encrypted |
| Metrics | `backup-metrics` (node-exporter, profile `monitoring`) | Age of the newest base backup and of the newest archived segment |
| Alerts | `infra/monitoring/alerts.yml` | `WalArchiveLag` (> 5 min) and `BaseBackupMissing` (> 26 h) |

## Daily check (2 minutes)

1. No `WalArchiveLag` or `BaseBackupMissing` alert in Alertmanager.
2. `docker compose -f infra/compose.prod.yml logs --since 24h backup | tail` shows `base backup … done` for last
   night.
3. If `BACKUP_REMOTE` is set: the newest directory is present on the second site.

## Quarterly drill (30 minutes)

The drill proves the backups can be restored, without touching production.

1. On a machine with PostgreSQL 16, PostGIS and pgvector: `sh infra/backup/drill.sh`. It builds two throwaway
   clusters and must end with `DRILL PASSED`, the RTO and the RPO.
2. Then restore a **real** backup the same way (step "Restore after a loss" below) into a throwaway data directory
   on a staging host, start it, and run `SELECT audit.verify_chain();` (NULL means intact) and
   `python -m app.modules.evidence verify`.
3. Write the date, the backup used, the RTO and the RPO in the operations log. A failure is an incident
   (`incident-response.md`, severity 2).

## Restore after a loss

Use this when the database is lost or corrupted, or to go back before a destructive mistake (point in time).

1. **Stop writes**: `docker compose -f infra/compose.prod.yml stop api worker`. The citizen app keeps reports in its
   offline queue and sends them when the API is back; it also offers the SMS fallback and the emergency numbers.
2. **Choose** the base backup: the newest one before the target time (`ls /archive/base`). For a point in time, note
   the target in the server's time zone, e.g. `2026-10-21 10:15:00+01`.
3. **Keep the broken data**: rename the `pgdata` volume or copy it aside. Never restore over it.
4. **Restore** into an empty directory, as the `postgres` user:
   ```sh
   infra/backup/restore.sh /archive/base/<date> /var/lib/postgresql/restored \
     [--target-time '2026-10-21 10:15:00+01'] --wal-dir /archive/wal
   ```
5. **Start** PostgreSQL on that directory. It replays the WAL up to the target (or to the end of the archive),
   promotes itself and opens. Follow the log until `database system is ready to accept connections`.
6. **Check**:
   * `SELECT audit.verify_chain();` returns NULL;
   * `python -m app.modules.evidence verify` reports no problem;
   * the last reports before the target are present.
7. **Point the services** at the restored cluster (swap the volume or the data directory), start `api` and
   `worker`, and watch the `ApiDown` and `ReportIntakeErrors` alerts clear.
8. **Take a base backup at once**: `docker compose -f infra/compose.prod.yml exec backup backup.sh once`. The new
   timeline starts here.
9. **Record**: time of the loss, target, backup used, measured RTO and RPO, and what was lost. If personal data was
   lost or exposed, follow `incident-response.md` (notification).

## When a step fails

* `restore: … base.tar.gz not found`: wrong directory, or the backup was still running; take the previous one.
* Recovery stops with `requested recovery stop point is before consistent recovery point`: the target is before the
  end of the chosen base backup; take an older base backup.
* A WAL segment is missing: the restore stops at the gap. Everything before it is consistent; record the gap as
  the actual RPO.
