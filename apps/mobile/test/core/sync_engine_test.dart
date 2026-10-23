// covers: FR-A-047, NFR-04
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
import 'package:ehimaya/core/http/api_error.dart';
import 'package:ehimaya/core/http/ehimaya_api.dart';
import 'package:ehimaya/core/http/models.dart';
import 'package:ehimaya/core/quota/anon_quota.dart';
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
      charterVersion: '2026-11',
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
  var quotas = <AnonQuota>[];
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
    quotas = <AnonQuota>[];
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
      onAnonQuota: quotas.add,
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
          'charter_version': '2026-11',
          'locale': 'ar',
          'platform': 'android',
        });
        return const FakeResponse(
          201,
          json: {'charter_version': '2026-11', 'accepted_at': 'x'},
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

    test('battery saver gate: the report goes at once, the media waits (no failure)', () async {
      final q = await enqueue(
        media: [
          DraftAttachment(
            path: audio.path,
            kind: MediaKind.audio,
            mime: 'audio/mp4',
          ),
        ],
      );
      var allow = false;
      var stored = 0;
      final gated = SyncEngine(
        db: db,
        api: EHimayaApi(
          Dio(BaseOptions(baseUrl: 'http://api.test'))
            ..httpClientAdapter = adapter,
        ),
        tus: TusClient(
          Dio(BaseOptions(baseUrl: 'http://tus.test/api/v1/uploads/'))
            ..httpClientAdapter = adapter,
          chunkSize: 1024,
        ),
        consent: consent,
        clock: () => now,
        identity: () => identity,
        onAnonBlocked: () {},
        mediaGate: (report, media) async => allow,
      );
      adapter.handler = (r) {
        if (r.uri.host == 'api.test' && r.method == 'POST') {
          return FakeResponse(201, json: serverReport(q.clientUuid));
        }
        if (r.method == 'POST') {
          return const FakeResponse(
            201,
            headers: {'Location': '/api/v1/uploads/abc'},
          );
        }
        if (r.method == 'PATCH') {
          stored += r.body!.length;
          return FakeResponse(204, headers: {'Upload-Offset': '$stored'});
        }
        return const FakeResponse(
          200,
          json: {'items': [], 'next_before': null},
        );
      };

      final first = await gated.runOnce();
      expect(first.reportsSent, 1);
      expect(first.failures, 0);
      var m = (await db.mediaForReport(q.clientUuid)).single;
      expect(m.state, MediaState.pending);
      expect(m.attempts, 0);
      expect(adapter.requests.where((r) => r.uri.host == 'tus.test'), isEmpty);

      allow = true;
      final second = await gated.runOnce();
      expect(second.mediaUploaded, 1);
      m = (await db.mediaForReport(q.clientUuid)).single;
      expect(m.state, MediaState.uploaded);
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

  group('on behalf of an institution (phase 4 §8)', () {
    const orgId = '7b0c6a2e-3d1f-4e55-9a10-1f2d3c4b5a60';

    setUp(() {
      identity = IdentityState(
        mode: IdentityMode.registered,
        role: UserRole.citizen,
        session: AuthSession(accessToken: 'a.b.c', expiresAt: DateTime(2100)),
      );
    });

    Future<QueuedReport> enqueueForOrg({String? organizationId = orgId}) =>
        queue.enqueue(
          ReportDraft(
            category: ReportCategory.fire,
            location: point,
            text: 'Feu',
            lang: 'fr',
            organizationId: organizationId,
          ),
        );

    test('online: organization_id is in the outgoing body', () async {
      final q = await enqueueForOrg();
      Object? body;
      adapter.handler = (r) {
        body = r.json;
        return FakeResponse(
          201,
          json: {
            ...serverReport(q.clientUuid),
            'organization': {'id': orgId, 'name': 'Société X'},
          },
        );
      };
      await engine.runOnce();
      expect((body! as Map)['organization_id'], orgId);
      expect((body! as Map)['client_uuid'], q.clientUuid);
      expect((await db.reportByUuid(q.clientUuid))!.state, ReportState.synced);
    });

    test('a report as myself carries no organization_id', () async {
      final q = await enqueueForOrg(organizationId: null);
      final row = (await db.reportByUuid(q.clientUuid))!;
      expect(jsonDecode(row.payload), isNot(contains('organization_id')));
      expect(payloadOrganizationId(row.payload), isNull);
    });

    test('offline: the choice is kept in the queue and sent at sync', () async {
      final q = await enqueueForOrg();
      expect(
        payloadOrganizationId((await db.reportByUuid(q.clientUuid))!.payload),
        orgId,
      );
      adapter.handler = (_) => const FakeResponse.network();
      await engine.runOnce();
      final row = (await db.reportByUuid(q.clientUuid))!;
      expect(row.state, ReportState.queued);

      now = row.nextAttemptAt!.add(const Duration(seconds: 1));
      Object? body;
      adapter.handler = (r) {
        body = r.json;
        return FakeResponse(201, json: serverReport(q.clientUuid));
      };
      await engine.runOnce();
      expect((body! as Map)['organization_id'], orgId);
      expect((await db.reportByUuid(q.clientUuid))!.state, ReportState.synced);
    });

    for (final (status, code) in [
      (404, 'org_not_found'),
      (409, 'org_not_active'),
    ]) {
      test(
        '$status $code: kept, not retried, resent as myself on request',
        () async {
          final q = await enqueueForOrg();
          adapter.handler = (_) => FakeResponse(status, json: {'detail': code});
          await engine.runOnce();
          var row = (await db.reportByUuid(q.clientUuid))!;
          expect(row.state, ReportState.orgRefused);
          expect(row.lastError, code);
          expect(row.nextAttemptAt, isNull);
          expect(payloadOrganizationId(row.payload), orgId); // never dropped

          // Not sent again on its own (no silent retry, no silent drop of the institution).
          adapter.requests.clear();
          now = now.add(const Duration(days: 1));
          await engine.runOnce();
          expect(
            adapter.requests.where((r) => r.path == '/api/v1/reports'),
            isEmpty,
          );

          // The user asks to send it as themselves: same client_uuid, no organization_id.
          expect(await queue.resendAsSelf(q.clientUuid), isTrue);
          row = (await db.reportByUuid(q.clientUuid))!;
          expect(row.state, ReportState.queued);
          expect(row.lastError, isNull);
          Object? body;
          adapter.handler = (r) {
            body = r.json;
            return FakeResponse(201, json: serverReport(q.clientUuid));
          };
          await engine.runOnce();
          expect(body, isNot(contains('organization_id')));
          expect((body! as Map)['client_uuid'], q.clientUuid);
          expect((body! as Map)['text'], 'Feu');
          expect(
            (await db.reportByUuid(q.clientUuid))!.state,
            ReportState.synced,
          );
        },
      );
    }

    test('resendAsSelf only applies to refused reports', () async {
      final q = await enqueueForOrg();
      expect(await queue.resendAsSelf(q.clientUuid), isFalse);
      expect(
        payloadOrganizationId((await db.reportByUuid(q.clientUuid))!.payload),
        orgId,
      );
    });

    test('never sent anonymously: waits for a signed-in account', () async {
      final q = await enqueueForOrg();
      identity = const IdentityState(
        mode: IdentityMode.anonymous,
        role: UserRole.citizen,
      );
      adapter.handler = (_) =>
          FakeResponse(201, json: serverReport(q.clientUuid));
      await engine.runOnce();
      expect(
        adapter.requests.where((r) => r.path == '/api/v1/reports'),
        isEmpty,
      );
      expect((await db.reportByUuid(q.clientUuid))!.state, ReportState.queued);
    });
  });
  group('anonymous quota (phase 9 §3)', () {
    const registered = IdentityState(
      mode: IdentityMode.registered,
      role: UserRole.citizen,
    );
    IdentityState signedIn() => IdentityState(
      mode: registered.mode,
      role: registered.role,
      session: AuthSession(accessToken: 'a.b.c', expiresAt: DateTime(2100)),
    );

    test('accepted report stores X-Anon-Quota-Remaining', () async {
      final q = await enqueue();
      adapter.handler = (_) => FakeResponse(
        201,
        json: serverReport(q.clientUuid),
        headers: const {
          'x-anon-quota-limit': '5',
          'x-anon-quota-remaining': '2',
        },
      );
      await engine.runOnce();
      expect((await db.reportByUuid(q.clientUuid))!.state, ReportState.synced);
      expect(quotas, [const AnonQuota(limit: 5, remaining: 2)]);
    });

    test('no quota headers (registered account): nothing stored', () async {
      final q = await enqueue();
      adapter.handler = (_) =>
          FakeResponse(201, json: serverReport(q.clientUuid));
      await engine.runOnce();
      expect(quotas, isEmpty);
    });

    test(
      'quota_exhausted_keeps_report_blocked_and_resends_after_login',
      () async {
        final q = await enqueue();
        adapter.handler = (_) => const FakeResponse(
          403,
          json: {'detail': 'anon_quota_exhausted'},
          headers: {'x-anon-quota-limit': '5', 'x-anon-quota-remaining': '0'},
        );
        await engine.runOnce();
        var row = (await db.reportByUuid(q.clientUuid))!;
        // Kept (never failed for good), with its payload, and the UI learns the quota is 0.
        expect(row.state, ReportState.blocked);
        expect(row.lastError, ApiErrorCode.anonQuotaExhausted.wire);
        expect(row.nextAttemptAt, isNull);
        expect(row.payload, contains('Feu de forêt'));
        expect(quotas, [const AnonQuota(limit: 5, remaining: 0)]);
        // Quarantine (anon_blocked) is a different situation: its banner is not raised.
        expect(blockedCalls, 0);

        // Still anonymous: not retried.
        adapter.requests.clear();
        await engine.runOnce();
        expect(adapter.requests, isEmpty);

        // After registration the same report (same client_uuid) is sent.
        identity = signedIn();
        adapter.handler = (r) {
          expect((r.json! as Map)['client_uuid'], q.clientUuid);
          return FakeResponse(201, json: serverReport(q.clientUuid));
        };
        await engine.runOnce();
        row = (await db.reportByUuid(q.clientUuid))!;
        expect(row.state, ReportState.synced);
        expect(row.serverTrackingCode, 'EH-26-61-0004821');
        expect(row.lastError, isNull);
      },
    );

    test('a 403 without quota headers still records 0 left', () async {
      await enqueue();
      adapter.handler = (_) =>
          const FakeResponse(403, json: {'detail': 'anon_quota_exhausted'});
      await engine.runOnce();
      expect(quotas, [const AnonQuota(limit: null, remaining: 0)]);
    });

    test('a report kept on the device (quota known exhausted) waits for an '
        'account, then goes', () async {
      final q = await queue.enqueue(
        const ReportDraft(
          category: ReportCategory.fire,
          location: point,
          text: 'Feu de forêt',
        ),
        blocked: true,
      );
      var row = (await db.reportByUuid(q.clientUuid))!;
      expect(row.state, ReportState.blocked);
      expect(row.lastError, ApiErrorCode.anonQuotaExhausted.wire);
      expect(row.lastError, anonQuotaExhaustedWire);
      adapter.handler = (_) =>
          FakeResponse(201, json: serverReport(q.clientUuid));
      await engine.runOnce();
      expect(adapter.requests, isEmpty);

      identity = signedIn();
      await engine.runOnce();
      row = (await db.reportByUuid(q.clientUuid))!;
      expect(row.state, ReportState.synced);
    });

    test('SOS beyond the quota is sent at once and accepted', () async {
      final q = await queue.enqueue(
        const ReportDraft(category: ReportCategory.sos, location: point),
      );
      final other = await enqueue();
      adapter.handler = (r) {
        final body = r.json! as Map;
        if (body['category'] == 'sos') {
          return FakeResponse(
            201,
            json: serverReport(q.clientUuid, category: 'sos'),
            headers: const {
              'x-anon-quota-limit': '5',
              'x-anon-quota-remaining': '0',
            },
          );
        }
        return const FakeResponse(
          403,
          json: {'detail': 'anon_quota_exhausted'},
          headers: {'x-anon-quota-limit': '5', 'x-anon-quota-remaining': '0'},
        );
      };
      await engine.runOnce();
      // SOS first, accepted; the ordinary report is kept for later.
      expect(
        (jsonDecode(adapter.requests.first.text) as Map)['category'],
        'sos',
      );
      expect((await db.reportByUuid(q.clientUuid))!.state, ReportState.synced);
      expect(
        (await db.reportByUuid(other.clientUuid))!.state,
        ReportState.blocked,
      );
    });
  });
}
