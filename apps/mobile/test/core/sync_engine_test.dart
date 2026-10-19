import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:dio/dio.dart';
import 'package:drift/drift.dart' show driftRuntimeOptions;
import 'package:ehimaya/core/auth/auth_session.dart';
import 'package:ehimaya/core/auth/identity.dart';
import 'package:ehimaya/core/consent/consent_service.dart';
import 'package:ehimaya/core/db/app_database.dart';
import 'package:ehimaya/core/db/open_database.dart';
import 'package:ehimaya/core/http/ehimaya_api.dart';
import 'package:ehimaya/core/http/models.dart';
import 'package:ehimaya/core/sync/backoff.dart';
import 'package:ehimaya/core/sync/report_queue.dart';
import 'package:ehimaya/core/sync/sync_engine.dart';
import 'package:ehimaya/core/tus/tus_client.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/fake_http.dart';

class RecordingConsent implements ConsentSender {
  RecordingConsent(this.api);
  final EHimayaApi api;
  int forced = 0;

  @override
  Future<bool> sendIfNeeded({bool force = false}) async {
    if (!force) return true;
    forced++;
    await api.postConsent(
      charterVersion: '2026-10',
      locale: 'ar',
      platform: 'android',
    );
    return true;
  }
}

Map<String, Object?> serverReport(
  String clientUuid, {
  String id = 'srv-1',
  String code = 'EH-26-61-0004821',
  String status = 'received',
  List<Map<String, Object?>> media = const [],
  String category = 'fire',
}) => {
  'id': id,
  'tracking_code': code,
  'client_uuid': clientUuid,
  'category': category,
  'status': status,
  'text': null,
  'lang': 'ar',
  'location': {'lat': 34.74, 'lon': 10.76, 'accuracy_m': 12.5},
  'gouvernorat_code': 61,
  'created_at': '2026-10-19T10:15:00Z',
  'received_at': '2026-10-19T10:15:02Z',
  'updated_at': '2026-10-19T10:15:02Z',
  'media': media,
};

void main() {
  driftRuntimeOptions.dontWarnAboutMultipleDatabases = true;

  late AppDatabase db;
  late Directory tmp;
  late FakeAdapter adapter;
  late DateTime now;
  late ReportQueue queue;
  late SyncEngine engine;
  late RecordingConsent consent;
  var blockedCalls = 0;
  var identity = const IdentityState(
    mode: IdentityMode.anonymous,
    role: UserRole.citizen,
  );

  setUp(() async {
    db = inMemoryDatabase();
    tmp = await Directory.systemTemp.createTemp('sync_test');
    now = DateTime.utc(2026, 10, 19, 10, 15);
    adapter = FakeAdapter((_) => const FakeResponse(500));
    final apiDio = Dio(BaseOptions(baseUrl: 'http://api.test'))
      ..httpClientAdapter = adapter;
    final tusDio = Dio(BaseOptions(baseUrl: 'http://tus.test/api/v1/uploads/'))
      ..httpClientAdapter = adapter;
    final api = EHimayaApi(apiDio);
    consent = RecordingConsent(api);
    blockedCalls = 0;
    identity = const IdentityState(
      mode: IdentityMode.anonymous,
      role: UserRole.citizen,
    );
    queue = ReportQueue(
      db: db,
      mediaDir: () async => Directory('${tmp.path}/media'),
      clock: () => now,
      random: Random(1),
    );
    engine = SyncEngine(
      db: db,
      api: api,
      tus: TusClient(tusDio, chunkSize: 1024),
      consent: consent,
      clock: () => now,
      identity: () => identity,
      onAnonBlocked: () => blockedCalls++,
      random: Random(7),
    );
  });

  tearDown(() async {
    await db.close();
    await tmp.delete(recursive: true);
  });

  const point = GeoPoint(lat: 34.74, lon: 10.76, accuracyM: 12.5);

  Future<QueuedReport> enqueue({List<DraftAttachment> media = const []}) =>
      queue.enqueue(
        ReportDraft(
          category: ReportCategory.fire,
          location: point,
          text: 'Feu de forêt',
          lang: 'fr',
          attachments: media,
        ),
      );

  test('temporary code format', () async {
    final q = await enqueue();
    expect(ReportQueue.tempCodeFormat.hasMatch(q.tempCode), isTrue);
    final row = await db.reportByUuid(q.clientUuid);
    expect(row!.state, ReportState.queued);
    final payload = jsonDecode(row.payload) as Map<String, Object?>;
    expect(payload['client_uuid'], q.clientUuid);
    expect(payload['category'], 'fire');
    expect(payload['lang'], 'fr');
    expect(payload['location'], {
      'lat': 34.74,
      'lon': 10.76,
      'accuracy_m': 12.5,
    });
  });

  test('idempotent retry: same client_uuid, 200 treated as 201, temp code replaced', () async {
    final q = await enqueue();
    adapter.handler = (_) => const FakeResponse.network();
    await engine.runOnce();

    var row = (await db.reportByUuid(q.clientUuid))!;
    expect(row.state, ReportState.queued);
    expect(row.attempts, 1);
    expect(row.lastError, 'network');
    expect(row.nextAttemptAt!.isAfter(now), isTrue);

    // Not due yet: nothing is sent.
    adapter.requests.clear();
    await engine.runOnce();
    expect(adapter.requests, isEmpty);

    // Later, the server already had it (the first answer was lost): 200 + same report.
    now = row.nextAttemptAt!.add(const Duration(seconds: 1));
    adapter.handler = (r) {
      expect(r.path, '/api/v1/reports');
      expect((r.json! as Map)['client_uuid'], q.clientUuid);
      return FakeResponse(200, json: serverReport(q.clientUuid));
    };
    await engine.runOnce();
    row = (await db.reportByUuid(q.clientUuid))!;
    expect(row.serverId, 'srv-1');
    expect(row.serverTrackingCode, 'EH-26-61-0004821');
    expect(row.tempCode, q.tempCode); // kept for reference
    expect(row.state, ReportState.synced);
    expect(row.attempts, 0);
    expect(row.lastError, isNull);
  });

  test('428 consent_required: consent is re-sent, then the report', () async {
    final q = await enqueue();
    var reportCalls = 0;
    adapter.handler = (r) {
      if (r.path == '/api/v1/consents') {
        expect(r.json, {
          'charter_version': '2026-10',
          'locale': 'ar',
          'platform': 'android',
        });
        return const FakeResponse(
          201,
          json: {'charter_version': '2026-10', 'accepted_at': 'x'},
        );
      }
      reportCalls++;
      return reportCalls == 1
          ? const FakeResponse(428, json: {'detail': 'consent_required'})
          : FakeResponse(201, json: serverReport(q.clientUuid));
    };
    await engine.runOnce();
    expect(adapter.requests.map((r) => r.path).toList(), [
      '/api/v1/reports',
      '/api/v1/consents',
      '/api/v1/reports',
    ]);
    expect(consent.forced, 1);
    final row = (await db.reportByUuid(q.clientUuid))!;
    expect(row.serverTrackingCode, 'EH-26-61-0004821');
  });

  test('back-off grows exponentially with jitter, capped, Retry-After floor', () {
    final rnd = Random(3);
    for (var attempt = 1; attempt <= 12; attempt++) {
      final full = min(5000 * pow(2, attempt - 1), 30 * 60 * 1000).toInt();
      final d = backoffDelay(attempt, rnd).inMilliseconds;
      expect(d, inInclusiveRange(full ~/ 2, full));
    }
    expect(
      backoffDelay(1, rnd, retryAfter: const Duration(minutes: 2)),
      const Duration(minutes: 2),
    );
    // Two phones with the same attempt count do not retry at the same instant.
    final a = backoffDelay(6, Random(1));
    final b = backoffDelay(6, Random(2));
    expect(a, isNot(b));
  });

  test('rate limiting uses Retry-After and keeps the report queued', () async {
    final q = await enqueue();
    adapter.handler = (_) => const FakeResponse(
      429,
      json: {'detail': 'rate_limited'},
      headers: {'Retry-After': '600'},
    );
    await engine.runOnce();
    final row = (await db.reportByUuid(q.clientUuid))!;
    expect(row.state, ReportState.queued);
    expect(
      row.nextAttemptAt!.isAtSameMomentAs(
        now.add(const Duration(seconds: 600)),
      ),
      isTrue,
    );
  });

  test('anon_blocked marks the report blocked and alerts the UI', () async {
    final q = await enqueue();
    adapter.handler = (_) =>
        const FakeResponse(403, json: {'detail': 'anon_blocked'});
    await engine.runOnce();
    expect(blockedCalls, 1);
    expect((await db.reportByUuid(q.clientUuid))!.state, ReportState.blocked);

    // Still anonymous: not retried. After registration it is sent again.
    adapter.requests.clear();
    await engine.runOnce();
    expect(adapter.requests, isEmpty);
    identity = IdentityState(
      mode: IdentityMode.registered,
      role: UserRole.citizen,
      session: AuthSession(accessToken: 'a.b.c', expiresAt: DateTime(2100)),
    );
    adapter.handler = (_) =>
        FakeResponse(201, json: serverReport(q.clientUuid));
    await engine.runOnce();
    expect((await db.reportByUuid(q.clientUuid))!.state, ReportState.synced);
  });

  test('client_uuid conflict: local copy kept, flagged, not retried', () async {
    final q = await enqueue();
    adapter.handler = (_) =>
        const FakeResponse(409, json: {'detail': 'client_uuid_conflict'});
    await engine.runOnce();
    final row = (await db.reportByUuid(q.clientUuid))!;
    expect(row.state, ReportState.conflict);
    expect(row.payload, contains('Feu de forêt'));
  });

  test(
    'replayed report that differs on the server: server wins, snapshot kept',
    () async {
      final q = await enqueue();
      adapter.handler = (_) => FakeResponse(
        200,
        json: serverReport(
          q.clientUuid,
          category: 'flood',
          status: 'in_progress',
        ),
      );
      await engine.runOnce();
      final row = (await db.reportByUuid(q.clientUuid))!;
      expect(row.serverStatus, 'in_progress');
      expect(row.serverSnapshot, contains('flood'));
      expect(row.payload, contains('"fire"'));
    },
  );

  group('media', () {
    late File audio;

    setUp(() async {
      audio = File('${tmp.path}/voice.m4a')
        ..writeAsBytesSync(List.generate(2500, (i) => i % 7));
    });

    test('report first, then tus upload, file deleted once stored', () async {
      final q = await enqueue(
        media: [
          DraftAttachment(
            path: audio.path,
            kind: MediaKind.audio,
            mime: 'audio/mp4',
          ),
        ],
      );
      final item = (await db.mediaForReport(q.clientUuid)).single;
      expect(item.sha256, await sha256OfFile(audio));
      expect(item.size, 2500);

      var stored = 0;
      var mediaStatus = 'verifying';
      adapter.handler = (r) {
        if (r.uri.host == 'api.test' && r.method == 'POST') {
          return FakeResponse(201, json: serverReport(q.clientUuid));
        }
        if (r.uri.host == 'api.test' && r.path == '/api/v1/reports/mine') {
          return FakeResponse(
            200,
            json: {
              'items': [
                serverReport(
                  q.clientUuid,
                  media: [
                    {
                      'id': 'm1',
                      'kind': 'audio',
                      'bytes': 2500,
                      'sha256': item.sha256,
                      'status': mediaStatus,
                    },
                  ],
                ),
              ],
              'next_before': null,
            },
          );
        }
        switch (r.method) {
          case 'POST':
            final meta = r.header('Upload-Metadata')!;
            expect(
              meta,
              contains('report_id ${base64.encode(utf8.encode('srv-1'))}'),
            );
            expect(
              meta,
              contains('sha256 ${base64.encode(utf8.encode(item.sha256))}'),
            );
            expect(r.header('Upload-Length'), '2500');
            return const FakeResponse(
              201,
              headers: {'Location': '/api/v1/uploads/abc'},
            );
          case 'PATCH':
            stored += r.body!.length;
            return FakeResponse(204, headers: {'Upload-Offset': '$stored'});
        }
        return const FakeResponse(500);
      };

      await engine.runOnce();
      var m = (await db.mediaForReport(q.clientUuid)).single;
      expect(m.state, MediaState.uploaded);
      expect(m.uploadOffset, 2500);
      expect(m.uploadUrl, 'http://tus.test/api/v1/uploads/abc');
      // Still verifying on the server: the local copy stays.
      expect(File(m.path).existsSync(), isTrue);
      expect((await db.reportByUuid(q.clientUuid))!.state, ReportState.created);

      mediaStatus = 'stored';
      await engine.runOnce();
      m = (await db.mediaForReport(q.clientUuid)).single;
      expect(m.state, MediaState.stored);
      expect(File(m.path).existsSync(), isFalse);
      expect((await db.reportByUuid(q.clientUuid))!.state, ReportState.synced);
    });

    test(
      'refused upload creation (409 upload_window_closed) is final',
      () async {
        final q = await enqueue(
          media: [
            DraftAttachment(
              path: audio.path,
              kind: MediaKind.audio,
              mime: 'audio/mp4',
            ),
          ],
        );
        adapter.handler = (r) {
          if (r.uri.host == 'api.test') {
            return FakeResponse(201, json: serverReport(q.clientUuid));
          }
          return const FakeResponse(
            409,
            json: {'detail': 'upload_window_closed'},
          );
        };
        await engine.runOnce();
        final m = (await db.mediaForReport(q.clientUuid)).single;
        expect(m.state, MediaState.failed);
        expect(m.lastError, 'upload_window_closed');
        expect(
          (await db.reportByUuid(q.clientUuid))!.state,
          ReportState.synced,
        );
        expect(File(m.path).existsSync(), isTrue);
      },
    );

    test('network failure during upload is retried later from HEAD', () async {
      final q = await enqueue(
        media: [
          DraftAttachment(
            path: audio.path,
            kind: MediaKind.audio,
            mime: 'audio/mp4',
          ),
        ],
      );
      var stored = 0;
      var online = true;
      var dropped = false;
      adapter.handler = (r) {
        if (r.uri.host == 'api.test') {
          return FakeResponse(201, json: serverReport(q.clientUuid));
        }
        if (!online) return const FakeResponse.network();
        switch (r.method) {
          case 'POST':
            return const FakeResponse(
              201,
              headers: {'Location': 'http://tus.test/api/v1/uploads/x'},
            );
          case 'HEAD':
            return FakeResponse(200, headers: {'Upload-Offset': '$stored'});
          case 'PATCH':
            stored += r.body!.length;
            if (!dropped) {
              dropped = true;
              online = false; // connection lost after the first chunk
            }
            return FakeResponse(204, headers: {'Upload-Offset': '$stored'});
        }
        return const FakeResponse(500);
      };
      await engine.runOnce();
      var m = (await db.mediaForReport(q.clientUuid)).single;
      expect(m.state, MediaState.pending);
      expect(m.uploadOffset, 1024);
      expect(m.attempts, 1);
      expect(m.nextAttemptAt, isNotNull);

      online = true;
      now = m.nextAttemptAt!.add(const Duration(seconds: 1));
      adapter.requests.clear();
      await engine.runOnce();
      m = (await db.mediaForReport(q.clientUuid)).single;
      expect(m.state, MediaState.uploaded);
      expect(
        adapter.requests.where(
          (r) => r.method == 'POST' && r.uri.host == 'tus.test',
        ),
        isEmpty,
      );
      expect(adapter.requests.first.method, 'HEAD');
      expect(stored, 2500);
    });
  });
}
