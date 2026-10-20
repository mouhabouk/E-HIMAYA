import 'package:drift/drift.dart';

part 'app_database.g.dart';

/// Lifecycle of a queued report.
abstract final class ReportState {
  /// Saved locally, not yet accepted by the server.
  static const queued = 'queued';

  /// The server returned a report id and tracking code; media may still be uploading.
  static const created = 'created';

  /// Report and all media stored on the server.
  static const synced = 'synced';

  /// `409 client_uuid_conflict`: the server copy wins, the local copy is kept for the user.
  static const conflict = 'conflict';

  /// Permanent refusal (validation error); kept locally, not retried.
  static const failed = 'failed';

  /// `403 anon_blocked`, or `403 anon_quota_exhausted` (phase 9 §3, also set on the device
  /// before queuing when the known quota is exhausted): waits until the user registers.
  static const blocked = 'blocked';

  /// Sent on behalf of an institution and refused (`404 org_not_found`, `409 org_not_active`):
  /// kept locally until the user resends it as themselves (phase 4 §8).
  static const orgRefused = 'org_refused';

  static const pendingStates = [queued, created, blocked];
}

abstract final class MediaState {
  static const pending = 'pending';
  static const uploading = 'uploading';

  /// All bytes accepted by tusd; waiting for the server to confirm `stored`.
  static const uploaded = 'uploaded';
  static const stored = 'stored';
  static const rejected = 'rejected';

  /// Permanent upload failure (too late, too big, refused).
  static const failed = 'failed';

  static const terminal = [stored, rejected, failed];
}

/// Offline queue of reports (FR-A-047, NFR-04).
@DataClassName('PendingReport')
class PendingReports extends Table {
  TextColumn get clientUuid => text()();
  TextColumn get category => text()();

  /// JSON body of `POST /api/v1/reports`, frozen at submit time.
  TextColumn get payload => text()();
  TextColumn get tempCode => text()();
  TextColumn get serverId => text().nullable()();
  TextColumn get serverTrackingCode => text().nullable()();
  TextColumn get serverStatus => text().nullable()();

  /// Server JSON of the report when it differs from the local copy (conflict, server wins).
  TextColumn get serverSnapshot => text().nullable()();
  TextColumn get state => text().withDefault(const Constant('queued'))();
  IntColumn get attempts => integer().withDefault(const Constant(0))();
  TextColumn get lastError => text().nullable()();
  DateTimeColumn get nextAttemptAt => dateTime().nullable()();
  DateTimeColumn get createdAt => dateTime()();
  DateTimeColumn get updatedAt => dateTime()();

  @override
  Set<Column<Object>> get primaryKey => {clientUuid};
}

@DataClassName('MediaItem')
class MediaItems extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get reportUuid => text().references(PendingReports, #clientUuid)();
  TextColumn get path => text()();

  /// `image` | `video` | `audio`.
  TextColumn get kind => text()();
  TextColumn get mime => text()();
  IntColumn get size => integer()();

  /// Lowercase hex SHA-256 of the whole file, computed by streaming.
  TextColumn get sha256 => text()();
  TextColumn get uploadUrl => text().nullable()();
  IntColumn get uploadOffset => integer().withDefault(const Constant(0))();
  TextColumn get state => text().withDefault(const Constant('pending'))();
  IntColumn get attempts => integer().withDefault(const Constant(0))();
  TextColumn get lastError => text().nullable()();
  DateTimeColumn get nextAttemptAt => dateTime().nullable()();
}

@DriftDatabase(tables: [PendingReports, MediaItems])
class AppDatabase extends _$AppDatabase {
  AppDatabase(super.executor);

  @override
  int get schemaVersion => 1;

  @override
  MigrationStrategy get migration => MigrationStrategy(
    beforeOpen: (details) async {
      await customStatement('PRAGMA foreign_keys = ON');
    },
  );

  // ---- reports ----------------------------------------------------------------------------

  Future<void> insertReport(
    PendingReportsCompanion report,
    List<MediaItemsCompanion> media,
  ) => transaction(() async {
    await into(pendingReports).insert(report);
    for (final m in media) {
      await into(mediaItems).insert(m);
    }
  });

  Future<PendingReport?> reportByUuid(String uuid) => (select(
    pendingReports,
  )..where((r) => r.clientUuid.equals(uuid))).getSingleOrNull();

  /// Reports the sync engine still has work for.
  Future<List<PendingReport>> reportsNeedingSync() =>
      (select(pendingReports)
            ..where((r) => r.state.isIn(ReportState.pendingStates))
            ..orderBy([(r) => OrderingTerm.asc(r.createdAt)]))
          .get();

  Stream<List<PendingReport>> watchAllReports() => (select(
    pendingReports,
  )..orderBy([(r) => OrderingTerm.desc(r.createdAt)])).watch();

  Future<void> updateReport(String uuid, PendingReportsCompanion changes) =>
      (update(
        pendingReports,
      )..where((r) => r.clientUuid.equals(uuid))).write(changes);

  // ---- media --------------------------------------------------------------------------------

  Future<List<MediaItem>> mediaForReport(String uuid) =>
      (select(mediaItems)
            ..where((m) => m.reportUuid.equals(uuid))
            ..orderBy([(m) => OrderingTerm.asc(m.id)]))
          .get();

  Stream<List<MediaItem>> watchAllMedia() => select(mediaItems).watch();

  Future<void> updateMedia(int id, MediaItemsCompanion changes) =>
      (update(mediaItems)..where((m) => m.id.equals(id))).write(changes);
}
