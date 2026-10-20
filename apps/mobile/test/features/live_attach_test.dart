import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:drift/drift.dart' show Value, driftRuntimeOptions;
import 'package:ehimaya/core/db/app_database.dart';
import 'package:ehimaya/core/db/open_database.dart';
import 'package:ehimaya/core/http/models.dart';
import 'package:ehimaya/core/media/media_rules.dart';
import 'package:ehimaya/core/sync/report_queue.dart';
import 'package:ehimaya/features/live/live_controller.dart';
import 'package:ehimaya/features/reports/reports_providers.dart';
import 'package:flutter_test/flutter_test.dart';

/// FR-A-051: the clip recorded instead of a live stream joins the report through the queue.
void main() {
  driftRuntimeOptions.dontWarnAboutMultipleDatabases = true;
  late AppDatabase db;
  late Directory tmp;
  late ReportQueue queue;
  late File clip;
  final now = DateTime.utc(2026, 10, 19, 10, 15);

  setUp(() async {
    db = inMemoryDatabase();
    tmp = await Directory.systemTemp.createTemp('live_attach');
    queue = ReportQueue(
      db: db,
      mediaDir: () async => Directory('${tmp.path}/media'),
      clock: () => now,
      random: Random(3),
    );
    clip = File('${tmp.path}/clip.mp4')..writeAsBytesSync(utf8.encode('mp4'));
  });

  tearDown(() async {
    await db.close();
    await tmp.delete(recursive: true);
  });

  DraftAttachment video() => DraftAttachment(
    path: clip.path,
    kind: MediaKind.video,
    mime: 'video/mp4',
  );

  test(
    'a synced report goes back to created so the clip is uploaded',
    () async {
      final queued = await queue.enqueue(
        const ReportDraft(
          category: ReportCategory.fire,
          location: GeoPoint(lat: 36.8, lon: 10.18),
        ),
      );
      await db.updateReport(
        queued.clientUuid,
        const PendingReportsCompanion(
          serverId: Value('rep-1'),
          state: Value(ReportState.synced),
        ),
      );
      final uuid = await queue.attach(
        AttachTarget(clientUuid: queued.clientUuid),
        video(),
      );
      expect(uuid, queued.clientUuid);
      final media = await db.mediaForReport(uuid);
      expect(media.single.kind, 'video');
      expect(media.single.state, MediaState.pending);
      expect(media.single.sha256, hasLength(64));
      expect(File(media.single.path).existsSync(), isTrue);
      expect((await db.reportByUuid(uuid))!.state, ReportState.created);
      // The source is the recorder's file: kept unless asked otherwise.
      expect(clip.existsSync(), isTrue);
    },
  );

  test('a report known only from the server gets a local row (no duplicate in the list)', () async {
    final uuid = await queue.attach(
      const AttachTarget(
        clientUuid: 'c-77',
        serverId: 'rep-77',
        trackingCode: 'EH-26-11-0000077',
        category: ReportCategory.flood,
      ),
      video(),
    );
    expect(uuid, 'c-77');
    final row = (await db.reportByUuid('c-77'))!;
    expect(row.serverId, 'rep-77');
    expect(row.state, ReportState.created);
    expect(row.category, 'flood');
    expect(await db.reportsNeedingSync(), hasLength(1));

    // Found again by server id the next time.
    final again = await queue.attach(
      const AttachTarget(serverId: 'rep-77'),
      video(),
    );
    expect(again, 'c-77');
    expect(await db.mediaForReport('c-77'), hasLength(2));

    final merged = mergeReports(
      local: [row],
      media: await db.mediaForReport('c-77'),
      server: [
        ServerReport.fromJson({
          'id': 'rep-77',
          'tracking_code': 'EH-26-11-0000077',
          'client_uuid': null,
          'category': 'flood',
          'status': 'in_progress',
          'media': [],
        }),
      ],
    );
    expect(merged, hasLength(1));
    expect(merged.single.serverId, 'rep-77');
    expect(merged.single.canGoLive, isTrue);
  });

  test('refused when unknown or full', () async {
    expect(
      () => queue.attach(const AttachTarget(clientUuid: 'nope'), video()),
      throwsArgumentError,
    );
    for (var i = 0; i < MediaRules.maxFilesPerReport; i++) {
      await queue.attach(const AttachTarget(serverId: 'rep-5'), video());
    }
    expect(
      () => queue.attach(const AttachTarget(serverId: 'rep-5'), video()),
      throwsArgumentError,
    );
  });

  test('closed and rejected reports cannot go live', () {
    ReportListItem item(ReportStatus? status, {String? serverId = 's'}) =>
        ReportListItem(
          trackingCode: 'EH',
          isTemporary: false,
          category: ReportCategory.fire,
          createdAt: now,
          serverId: serverId,
          status: status,
        );
    expect(item(ReportStatus.received).canGoLive, isTrue);
    expect(item(ReportStatus.ongoing).canGoLive, isTrue);
    expect(item(ReportStatus.closed).canGoLive, isFalse);
    expect(item(ReportStatus.rejected).canGoLive, isFalse);
    expect(item(null, serverId: null).canGoLive, isFalse);
  });

  test('live route parameters', () {
    expect(const LiveTarget.newReport().isNew, isTrue);
    expect(const LiveTarget.existing(serverId: 'r').isNew, isFalse);
  });
}
