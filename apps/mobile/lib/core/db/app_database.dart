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

/// Phase B2 (addition 5): personal emergency contacts. Kept on the phone only (this encrypted
/// database), never sent to the server. [linkId] is the server link when the contact also uses
/// e-Himaya and accepted an invitation (in-app alert).
@DataClassName('EmergencyContact')
class EmergencyContacts extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get name => text()();

  /// `+216XXXXXXXX`, or an international number with `+`.
  TextColumn get phone => text()();

  /// Comma-separated ids of [ContactGroups] (`,3,7,`), so a contact can sit in several groups.
  TextColumn get groups => text().withDefault(const Constant(','))();
  TextColumn get linkId => text().nullable()();
  IntColumn get position => integer().withDefault(const Constant(0))();
  DateTimeColumn get createdAt => dateTime()();

  /// Review point 6 (phase D): an optional e-mail, for the e-mail channel of the SOS message.
  TextColumn get email => text().nullable()();
}

@DataClassName('ContactGroup')
class ContactGroups extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get name => text()();
  IntColumn get position => integer().withDefault(const Constant(0))();
}

/// Phase B2 (8.7): what the phone sent, kept on the phone only.
@DataClassName('SafetyAlertEntry')
class SafetyAlertHistory extends Table {
  IntColumn get id => integer().autoIncrement()();

  /// `sos_message` | `safety_check` | `live_share`.
  TextColumn get kind => text()();
  DateTimeColumn get at => dateTime()();

  /// Comma-separated: `app`, `sms`, `whatsapp`.
  TextColumn get channels => text().withDefault(const Constant(''))();
  IntColumn get recipients => integer().withDefault(const Constant(0))();
  TextColumn get serverId => text().nullable()();

  /// `sent` | `cancelled` | `failed` | `ok` (a safety check answered).
  TextColumn get status => text()();
}

/// Phase B2 (addition 7b): the medical file, one row, kept on the phone only. [data] is the JSON
/// of the fields; [consentVersion] the 7b text the user accepted (no row without consent).
@DataClassName('MedicalProfileRow')
class MedicalProfiles extends Table {
  IntColumn get id => integer()();
  TextColumn get data => text()();
  TextColumn get consentVersion => text()();
  DateTimeColumn get consentAt => dateTime()();
  BoolColumn get locked => boolean().withDefault(const Constant(false))();
  DateTimeColumn get updatedAt => dateTime()();

  @override
  Set<Column<Object>> get primaryKey => {id};
}

@DriftDatabase(
  tables: [
    PendingReports,
    MediaItems,
    EmergencyContacts,
    ContactGroups,
    SafetyAlertHistory,
    MedicalProfiles,
  ],
)
class AppDatabase extends _$AppDatabase {
  AppDatabase(super.executor);

  /// 2 (phase B2): emergency contacts and groups, alert history, medical file.
  /// 3 (phase D): an optional e-mail per emergency contact.
  @override
  int get schemaVersion => 3;

  @override
  MigrationStrategy get migration => MigrationStrategy(
    onUpgrade: (m, from, to) async {
      // Each step only adds: the queued reports and media of version 1 are kept as they are.
      if (from < 2) {
        await m.createTable(emergencyContacts);
        await m.createTable(contactGroups);
        await m.createTable(safetyAlertHistory);
        await m.createTable(medicalProfiles);
      }
      if (from >= 2 && from < 3) {
        await m.addColumn(emergencyContacts, emergencyContacts.email);
      }
    },
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

  // ---- personal safety (phase B2) ------------------------------------------------------------

  Stream<List<EmergencyContact>> watchContacts() =>
      (select(emergencyContacts)..orderBy([
            (c) => OrderingTerm.asc(c.position),
            (c) => OrderingTerm.asc(c.id),
          ]))
          .watch();

  Future<List<EmergencyContact>> allContacts() =>
      (select(emergencyContacts)..orderBy([
            (c) => OrderingTerm.asc(c.position),
            (c) => OrderingTerm.asc(c.id),
          ]))
          .get();

  Future<int> addContact(EmergencyContactsCompanion c) =>
      into(emergencyContacts).insert(c);

  Future<void> updateContact(int id, EmergencyContactsCompanion c) =>
      (update(emergencyContacts)..where((r) => r.id.equals(id))).write(c);

  Future<void> deleteContact(int id) =>
      (delete(emergencyContacts)..where((r) => r.id.equals(id))).go();

  Stream<List<ContactGroup>> watchGroups() =>
      (select(contactGroups)..orderBy([
            (g) => OrderingTerm.asc(g.position),
            (g) => OrderingTerm.asc(g.id),
          ]))
          .watch();

  Future<int> addGroup(String name) =>
      into(contactGroups).insert(ContactGroupsCompanion.insert(name: name));

  /// Removes the group and takes it off every contact.
  Future<void> deleteGroup(int id) => transaction(() async {
    await (delete(contactGroups)..where((g) => g.id.equals(id))).go();
    for (final c in await allContacts()) {
      if (c.groups.contains(',$id,')) {
        await updateContact(
          c.id,
          EmergencyContactsCompanion(
            groups: Value(c.groups.replaceAll(',$id,', ',')),
          ),
        );
      }
    }
  });

  Future<int> addAlertHistory(SafetyAlertHistoryCompanion e) =>
      into(safetyAlertHistory).insert(e);

  Stream<List<SafetyAlertEntry>> watchAlertHistory() => (select(
    safetyAlertHistory,
  )..orderBy([(e) => OrderingTerm.desc(e.at)])).watch();

  Future<void> clearAlertHistory() => delete(safetyAlertHistory).go();

  Stream<MedicalProfileRow?> watchMedical() => (select(
    medicalProfiles,
  )..where((m) => m.id.equals(1))).watchSingleOrNull();

  Future<MedicalProfileRow?> medical() =>
      (select(medicalProfiles)..where((m) => m.id.equals(1))).getSingleOrNull();

  Future<void> saveMedical(MedicalProfilesCompanion m) =>
      into(medicalProfiles)
          .insertOnConflictUpdate(m.copyWith(id: const Value(1)));

  Future<void> deleteMedical() => delete(medicalProfiles).go();
}
