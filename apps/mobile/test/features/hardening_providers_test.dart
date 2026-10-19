import 'dart:io';

import 'package:drift/drift.dart' show driftRuntimeOptions;
import 'package:ehimaya/core/auth/identity.dart';
import 'package:ehimaya/core/connectivity/connectivity.dart';
import 'package:ehimaya/core/db/app_database.dart';
import 'package:ehimaya/core/db/open_database.dart';
import 'package:ehimaya/core/http/ehimaya_api.dart';
import 'package:ehimaya/core/http/models.dart';
import 'package:ehimaya/core/platform/device_services.dart';
import 'package:ehimaya/core/power/battery_saver.dart';
import 'package:ehimaya/core/power/scheduling.dart';
import 'package:ehimaya/core/push/push_messaging.dart';
import 'package:ehimaya/core/push/push_payload.dart';
import 'package:ehimaya/core/push/redacted_push.dart';
import 'package:ehimaya/core/storage/app_prefs.dart';
import 'package:ehimaya/core/storage/secure_store.dart';
import 'package:ehimaya/core/sync/report_queue.dart';
import 'package:ehimaya/features/alerts/alerts_providers.dart';
import 'package:ehimaya/features/privacy/account_deletion.dart';
import 'package:ehimaya/features/settings/alert_check.dart';
import 'package:ehimaya/features/volunteer/volunteer_providers.dart';
import 'package:ehimaya/l10n/app_localizations.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/fake_http.dart';
import '../helpers/hardening_fakes.dart';
import '../helpers/phase5_fixtures.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  driftRuntimeOptions.dontWarnAboutMultipleDatabases = true;

  group('battery saver', () {
    test('low battery activates it; charging and "off" turn it off', () async {
      final device = FakeDeviceServices(
        reading: const BatteryReading(level: 15, charging: false),
      );
      final c = await phase5Container(
        FakeAdapter((_) => const FakeResponse(404)),
        overrides: [deviceServicesProvider.overrideWithValue(device)],
      );
      expect(c.read(batterySaverActiveProvider), isFalse);
      await c.read(batterySaverProvider.notifier).refresh();
      expect(c.read(batterySaverActiveProvider), isTrue);
      expect(c.read(batterySaverProvider).reading?.level, 15);

      device.reading = const BatteryReading(level: 15, charging: true);
      await c.read(batterySaverProvider.notifier).refresh();
      expect(c.read(batterySaverActiveProvider), isFalse);

      await c.read(batterySaverProvider.notifier).setMode(BatterySaverMode.on);
      expect(c.read(batterySaverActiveProvider), isTrue);
      expect(prefsOf(c).batterySaverMode, 'on');
      await c.read(batterySaverProvider.notifier).setMode(BatterySaverMode.off);
      expect(c.read(batterySaverActiveProvider), isFalse);
    });
  });

  group('AlertsScheduler', () {
    late ControlledConnectivity net;
    late FakeAdapter adapter;
    var status = 200;

    setUp(() {
      status = 200;
      net = ControlledConnectivity();
      adapter = FakeAdapter(
        (r) => r.path == '/api/v1/alerts/active' && status == 200
            ? const FakeResponse(200, json: [])
            : FakeResponse(status),
      );
    });

    Future<AlertsScheduler> started() async {
      final c = await phase5Container(
        adapter,
        registered: false,
        overrides: [connectivityProvider.overrideWithValue(net)],
      );
      final scheduler = c.read(alertsSchedulerProvider);
      scheduler.start();
      return scheduler;
    }

    test('backs off after failures, resets on success', () async {
      final s = await started();
      expect(s.isScheduled, isTrue);
      // No push on this phone: 5 minutes.
      expect(s.period, const Duration(minutes: 5));
      status = 503;
      await s.refreshNow();
      expect(s.period, const Duration(minutes: 10));
      await s.refreshNow();
      expect(s.period, const Duration(minutes: 15));
      status = 200;
      await s.refreshNow();
      expect(s.period, const Duration(minutes: 5));
    });

    test('nothing runs in the background or offline', () async {
      final s = await started();
      s.didChangeAppLifecycleState(AppLifecycleState.paused);
      expect(s.isScheduled, isFalse);
      s.didChangeAppLifecycleState(AppLifecycleState.resumed);
      await Future<void>.delayed(Duration.zero);
      await pumpEventQueue();
      expect(s.isScheduled, isTrue);

      net.set(false);
      await pumpEventQueue();
      expect(s.isScheduled, isFalse);
      final before = adapter.requests.length;
      net.set(true);
      await pumpEventQueue();
      expect(adapter.requests.length, greaterThan(before));
      expect(s.isScheduled, isTrue);
    });
  });

  group('ReadinessTracker (coalesced sharing)', () {
    late Map<String, Object?> volunteer;
    late FakeAdapter adapter;
    late DateTime now;
    final sent = <Object?>[];

    setUp(() {
      now = DateTime.utc(2026, 10, 19, 10);
      sent.clear();
      volunteer = volunteerJson(
        ready: true,
        readyUntil: '2026-10-19T18:00:00Z',
      );
      adapter = FakeAdapter((r) {
        if (r.path == '/api/v1/me/volunteer') {
          return FakeResponse(200, json: volunteer);
        }
        if (r.path == '/api/v1/me/volunteer/location') {
          sent.add(r.json);
          return const FakeResponse(204);
        }
        return const FakeResponse(404);
      });
    });

    test('stationary: one send; a 150 m move is sent after 30 s', () async {
      final location = MovableLocation(
        const GeoPoint(lat: 34.7406, lon: 10.7603, accuracyM: 20),
      );
      final c = await phase5Container(
        adapter,
        clock: () => now,
        location: location,
      );
      await c.read(volunteerProvider.future);
      final tracker = c.read(readinessTrackerProvider);
      expect(await tracker.tick(), ReadinessTick.sent);
      now = now.add(const Duration(minutes: 2));
      expect(await tracker.tick(), ReadinessTick.unchanged);
      location.fix = const GeoPoint(lat: 34.7420, lon: 10.7603);
      now = now.add(const Duration(seconds: 10));
      expect(await tracker.tick(), ReadinessTick.sent);
      expect(sent, hasLength(2));
    });

    test(
      'stops at once in the background, restarts in the foreground',
      () async {
        final location = MovableLocation(
          const GeoPoint(lat: 34.7406, lon: 10.7603),
        );
        final c = await phase5Container(
          adapter,
          clock: () => now,
          location: location,
        );
        await c.read(volunteerProvider.future);
        final tracker = c.read(readinessTrackerProvider)..start();
        expect(tracker.isSharing, isTrue);
        expect(location.watchCalls, 1);
        tracker.didChangeAppLifecycleState(AppLifecycleState.paused);
        expect(tracker.isSharing, isFalse);
        tracker.didChangeAppLifecycleState(AppLifecycleState.resumed);
        expect(tracker.isSharing, isTrue);
        expect(location.watchCalls, 2);
      },
    );

    test('battery saver restarts the position stream in low power', () async {
      final location = MovableLocation(
        const GeoPoint(lat: 34.7406, lon: 10.7603),
      );
      final device = FakeDeviceServices(
        reading: const BatteryReading(level: 10, charging: false),
      );
      final c = await phase5Container(
        adapter,
        clock: () => now,
        location: location,
        overrides: [deviceServicesProvider.overrideWithValue(device)],
      );
      await c.read(volunteerProvider.future);
      c.read(readinessTrackerProvider).start();
      expect(location.watchCalls, 1);
      await c.read(batterySaverProvider.notifier).refresh();
      await pumpEventQueue();
      expect(c.read(batterySaverActiveProvider), isTrue);
      expect(location.watchCalls, 2);
    });
  });

  group('A8 redacted pushes', () {
    final l10n = lookupAppLocalizations(const Locale('en'));

    Future<RedactedPushResolver> resolver(FakeHandler handler) async {
      final c = await phase5Container(FakeAdapter(handler));
      return RedactedPushResolver(c.read(apiProvider), l10n);
    }

    test('call-out: fetched with the identity, shown on the phone', () async {
      final r = await resolver(
        (req) => req.path == '/api/v1/me/callouts'
            ? FakeResponse(200, json: [calloutJson(id: 'c1')])
            : const FakeResponse(404),
      );
      final resolved = await r.resolve(
        PushPayload.parse({
          'type': 'callout',
          'callout_id': 'c1',
          'redacted': '1',
        }, title: 'e-Himaya: you have an update')!,
      );
      expect(resolved!.title, 'Call-out · Fire');
      expect(resolved.body, contains('حريق في مستودع'));
      expect(resolved.body, contains('2.4 km'));
      expect(resolved.data['callout_id'], 'c1');
    });

    test('report status: tracking code and status label', () async {
      final r = await resolver(
        (req) => req.path == '/api/v1/reports/track/EH-26-61-0000001'
            ? const FakeResponse(
                200,
                json: {
                  'tracking_code': 'EH-26-61-0000001',
                  'status': 'in_progress',
                  'history': [],
                },
              )
            : const FakeResponse(404),
      );
      final resolved = await r.resolve(
        PushPayload.parse({
          'type': 'report_status',
          'tracking_code': 'EH-26-61-0000001',
          'redacted': '1',
        })!,
      );
      expect(resolved!.title, 'Report EH-26-61-0000001');
      expect(resolved.body, l10n.statusInProgress);
    });

    test('inbox message, in the UI language', () async {
      final r = await resolver(
        (req) => req.path == '/api/v1/notifications'
            ? FakeResponse(
                200,
                json: {
                  'items': [inboxItemJson('n1')],
                  'next_cursor': null,
                },
              )
            : const FakeResponse(404),
      );
      final resolved = await r.resolve(
        PushPayload.parse({'type': 'info', 'id': 'n1', 'redacted': '1'})!,
      );
      // No English text on the server: Arabic fallback.
      expect(resolved!.title, 'يوم تحسيسي');
    });

    test('not redacted, offline or gone: generic text kept (null)', () async {
      final r = await resolver((_) => const FakeResponse.network());
      expect(await r.resolve(PushPayload.parse({'type': 'callout'})!), isNull);
      expect(
        await r.resolve(
          PushPayload.parse({'type': 'callout', 'redacted': '1'})!,
        ),
        isNull,
      );
    });
  });

  group('alert issues', () {
    const blocked = AlertHealth(
      notificationsEnabled: false,
      channelImportance: {alertChannelId: 2},
      doNotDisturb: true,
      policyAccess: false,
      ignoringBatteryOptimizations: false,
      fullScreenIntentAllowed: false,
    );

    test('everything that may block alerts is listed', () {
      expect(
        alertIssues(
          blocked,
          pushAvailable: false,
          volunteerReady: true,
          criticalOptIn: false,
        ),
        AlertIssue.values,
      );
    });

    test('battery optimisation only matters for a ready volunteer', () {
      expect(
        alertIssues(
          blocked,
          pushAvailable: true,
          volunteerReady: false,
          criticalOptIn: false,
        ),
        isNot(contains(AlertIssue.batteryOptimized)),
      );
    });

    test('DND is fine once critical alerts are opted in with access', () {
      const dnd = AlertHealth(
        notificationsEnabled: true,
        channelImportance: {alertChannelId: 5},
        doNotDisturb: true,
        policyAccess: true,
      );
      expect(
        alertIssues(
          dnd,
          pushAvailable: true,
          volunteerReady: false,
          criticalOptIn: true,
        ),
        isEmpty,
      );
      expect(
        alertIssues(
          dnd,
          pushAvailable: true,
          volunteerReady: false,
          criticalOptIn: false,
        ),
        [AlertIssue.doNotDisturb],
      );
    });

    test('unknown platform answers are not reported', () {
      expect(
        alertIssues(
          const AlertHealth(),
          pushAvailable: true,
          volunteerReady: true,
          criticalOptIn: false,
        ),
        isEmpty,
      );
    });

    test('AlertHealth parses the platform map', () {
      final h = AlertHealth.fromMap({
        'notificationsEnabled': true,
        'channels': {alertChannelId: 4, 'x': 'bad'},
        'doNotDisturb': false,
        'fullScreenIntentAllowed': null,
      });
      expect(h.notificationsEnabled, isTrue);
      expect(h.channelImportance, {alertChannelId: 4});
      expect(h.doNotDisturb, isFalse);
      expect(h.fullScreenIntentAllowed, isNull);
    });
  });

  group('A6 citizen rights', () {
    test('export returns indented JSON', () async {
      final c = await phase5Container(
        FakeAdapter(
          (r) => r.path == '/api/v1/me/export'
              ? const FakeResponse(
                  200,
                  json: {
                    'profile': {'full_name': 'Amel'},
                  },
                )
              : const FakeResponse(404),
        ),
      );
      final json = await c.read(citizenRightsProvider).exportData();
      expect(json, contains('\n  "profile"'));
      expect(json, contains('Amel'));
    });

    test('delete: confirm sent, then the phone forgets the user', () async {
      final adapter = FakeAdapter(
        (r) => r.path == '/api/v1/me/delete'
            ? const FakeResponse(202, json: {'status': 'deleted'})
            : const FakeResponse(404),
      );
      final secure = MemorySecureStore({
        SecureStoreKeys.authSession: '{}',
        SecureStoreKeys.deviceKey: 'k' * 43,
        SecureStoreKeys.orgCache: '[]',
        SecureStoreKeys.dbKey: 'db',
      });
      final db = inMemoryDatabase();
      addTearDown(db.close);
      final media = Directory.systemTemp.createTempSync('wipe_media');
      File('${media.path}/photo.jpg').writeAsBytesSync([1, 2, 3]);
      final c = await phase5Container(
        adapter,
        prefs: {
          'settings.locale': 'fr',
          'alerts.last': '[]',
          'profile.prompted': true,
        },
        secure: secure,
        overrides: [
          databaseProvider.overrideWithValue(db),
          mediaDirProvider.overrideWithValue(() async => media),
        ],
      );
      await db
          .into(db.pendingReports)
          .insert(
            PendingReportsCompanion.insert(
              clientUuid: 'u1',
              tempCode: 'TMP-1',
              category: 'fire',
              payload: '{}',
              createdAt: DateTime.utc(2026, 10, 19),
              updatedAt: DateTime.utc(2026, 10, 19),
            ),
          );
      expect(c.read(identityProvider).isRegistered, isTrue);

      await c.read(citizenRightsProvider).deleteAccount();

      expect(lastTo(adapter, 'POST', '/api/v1/me/delete')!.json, {
        'confirm': 'DELETE',
      });
      expect(c.read(identityProvider).hasIdentity, isFalse);
      expect(c.read(identityProvider).role, isNull);
      expect(await db.select(db.pendingReports).get(), isEmpty);
      expect(media.existsSync(), isFalse);
      expect(secure.values.keys, [SecureStoreKeys.dbKey]);
      final prefs = prefsOf(c);
      expect(prefs.localeCode, 'fr');
      expect(prefs.charterAcceptedVersion, isNull);
      expect(prefs.lastAlertsJson, isNull);
      expect(prefs.profilePrompted, isFalse);
    });

    test('last admin of an institution: refused, explained, kept', () async {
      final c = await phase5Container(
        FakeAdapter(
          (_) => const FakeResponse(409, json: {'code': 'last_admin'}),
        ),
      );
      await expectLater(
        c.read(citizenRightsProvider).deleteAccount(),
        throwsA(isA<LastAdminException>()),
      );
      expect(c.read(identityProvider).isRegistered, isTrue);
    });

    test('refused by the server: nothing is wiped', () async {
      final c = await phase5Container(
        FakeAdapter((_) => const FakeResponse(503)),
      );
      await expectLater(
        c.read(citizenRightsProvider).deleteAccount(),
        throwsA(isA<Exception>()),
      );
      expect(c.read(identityProvider).isRegistered, isTrue);
      expect(prefsOf(c).charterAcceptedVersion, isNotNull);
    });
  });

  test('prefs: wipe keeps only the interface choices', () async {
    final c = await phase5Container(
      FakeAdapter((_) => const FakeResponse(404)),
      prefs: {'settings.theme': 'dark', 'power.battery_saver': 'on'},
    );
    final AppPrefs prefs = prefsOf(c);
    await prefs.wipeForAccountDeletion();
    expect(prefs.themeMode, 'dark');
    expect(prefs.batterySaverMode, 'on');
    expect(prefs.role, isNull);
  });
}
