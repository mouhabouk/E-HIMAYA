import 'package:drift/drift.dart' show driftRuntimeOptions;
import 'package:ehimaya/core/auth/auth_session.dart';
import 'package:ehimaya/core/auth/identity.dart';
import 'package:ehimaya/core/connectivity/connectivity.dart';
import 'package:ehimaya/core/db/app_database.dart';
import 'package:ehimaya/core/db/open_database.dart';
import 'package:ehimaya/core/http/api_error.dart';
import 'package:ehimaya/core/http/models.dart';
import 'package:ehimaya/core/power/scheduling.dart';
import 'package:ehimaya/core/quota/anon_quota.dart';
import 'package:ehimaya/core/quota/anon_quota_controller.dart';
import 'package:ehimaya/core/routing/app_router.dart';
import 'package:ehimaya/core/storage/app_prefs.dart';
import 'package:ehimaya/core/storage/secure_store.dart';
import 'package:ehimaya/core/sync/report_queue.dart';
import 'package:ehimaya/core/sync/sync_scheduler.dart';
import 'package:ehimaya/features/report/report_submit.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../helpers/app_harness.dart';
import '../helpers/fake_http.dart';

class _Offline implements ConnectivityMonitor {
  @override
  Future<bool> isOnline() async => false;
  @override
  Stream<bool> get onlineChanges => const Stream.empty();
  @override
  Future<NetworkKind> networkKind() async => NetworkKind.none;
}

/// Anonymous installation whose last known quota is [remaining] of [limit].
Map<String, Object> quotaPrefs({int remaining = 0, int limit = 5}) => {
  ...onboardedPrefs(locale: 'en'),
  'quota.anon_limit': limit,
  'quota.anon_remaining': remaining,
};

FakeHandler quotaApi({required int remaining, int limit = 5}) => (r) {
  if (r.path == '/api/v1/reports/quota') {
    return FakeResponse(
      200,
      json: {'limit': limit, 'used': limit - remaining, 'remaining': remaining},
    );
  }
  return defaultApiResponse(r);
};

Future<void> go(WidgetTester tester, String location) async {
  final context = tester.element(find.byType(Scaffold).first);
  ProviderScope.containerOf(context).read(routerProvider).go(location);
  await tester.pumpAndSettle();
}

void main() {
  group('quota card', () {
    testWidgets('home shows "N of 5 left" from GET /reports/quota on start', (
      tester,
    ) async {
      final h = await pumpApp(
        tester,
        prefs: onboardedPrefs(locale: 'en'),
        api: quotaApi(remaining: 2),
      );
      expect(
        h.adapter.requests.where((r) => r.path == '/api/v1/reports/quota'),
        hasLength(1),
      );
      await scrollHomeTo(tester, 'anon-quota-card');
      expect(find.byKey(const Key('anon-quota-card')), findsOneWidget);
      expect(find.text('2 of 5 left'), findsOneWidget);
      await unmountApp(tester);
    });

    testWidgets('offline on start: the last known value, no request', (
      tester,
    ) async {
      final h = await pumpApp(
        tester,
        prefs: quotaPrefs(remaining: 3),
        connectivity: _Offline(),
      );
      expect(
        h.adapter.requests.where((r) => r.path == '/api/v1/reports/quota'),
        isEmpty,
      );
      await scrollHomeTo(tester, 'anon-quota-card');
      expect(find.text('3 of 5 left'), findsOneWidget);
      await unmountApp(tester);
    });

    testWidgets('exhausted: card says so and opens the quota screen', (
      tester,
    ) async {
      await pumpApp(tester, prefs: quotaPrefs());
      await scrollHomeTo(tester, 'anon-quota-card');
      expect(find.textContaining('0 of 5 left'), findsOneWidget);
      await tester.ensureVisible(find.byKey(const Key('anon-quota-card')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('anon-quota-card')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('anon-quota-call-198')), findsOneWidget);
      expect(find.byKey(const Key('anon-quota-register')), findsOneWidget);
      await unmountApp(tester);
    });

    testWidgets('no card for a registered account', (tester) async {
      final h = await pumpApp(
        tester,
        prefs: registeredPrefs(locale: 'en'),
        session: testSession,
        api: quotaApi(remaining: 0),
      );
      expect(find.byKey(const Key('anon-quota-card')), findsNothing);
      expect(
        h.adapter.requests.where((r) => r.path == '/api/v1/reports/quota'),
        isEmpty,
      );
      await unmountApp(tester);
    });

    testWidgets('the report form shows the card too', (tester) async {
      await pumpApp(tester, prefs: quotaPrefs(remaining: 4));
      await go(tester, Routes.newReportFor(ReportCategory.fire));
      expect(find.byKey(const Key('anon-quota-card')), findsOneWidget);
      expect(find.text('4 of 5 left'), findsOneWidget);
      await unmountApp(tester);
    });
  });

  group('quota screen', () {
    testWidgets('shows_call_198: the call works offline, without an account', (
      tester,
    ) async {
      final h = await pumpApp(
        tester,
        prefs: quotaPrefs(),
        connectivity: _Offline(),
      );
      await go(tester, Routes.quota);
      expect(find.text('Call 198'), findsOneWidget);
      await tester.tap(find.byKey(const Key('anon-quota-call-198')));
      await tester.pumpAndSettle();
      expect(h.dialled, [Uri(scheme: 'tel', path: '198')]);
      await unmountApp(tester);
    });

    testWidgets('explains the limit and offers an account', (tester) async {
      await pumpApp(tester, prefs: quotaPrefs());
      await go(tester, Routes.quota);
      expect(find.byKey(const Key('anon-quota-screen-label')), findsOneWidget);
      expect(find.textContaining('limited number of reports'), findsOneWidget);
      expect(find.text('Create an account'), findsOneWidget);
      expect(find.text('I already have an account'), findsOneWidget);
      await unmountApp(tester);
    });
  });

  group('submit with the quota exhausted', () {
    Future<(ProviderContainer, AppDatabase, List<int>)> container(
      Map<String, Object> prefs, {
      AuthSession? session,
    }) async {
      driftRuntimeOptions.dontWarnAboutMultipleDatabases = true;
      SharedPreferences.setMockInitialValues(prefs);
      final sp = await SharedPreferences.getInstance();
      final db = inMemoryDatabase();
      final syncs = <int>[];
      final c = ProviderContainer(
        overrides: [
          sharedPreferencesProvider.overrideWithValue(sp),
          secureStoreProvider.overrideWithValue(MemorySecureStore()),
          initialAuthSessionProvider.overrideWithValue(session),
          databaseProvider.overrideWithValue(db),
          requestSyncProvider.overrideWithValue(() async => syncs.add(1)),
        ],
      );
      addTearDown(() async {
        c.dispose();
        await db.close();
      });
      return (c, db, syncs);
    }

    const draft = ReportDraft(
      category: ReportCategory.fire,
      location: GeoPoint(lat: 36.8, lon: 10.18, accuracyM: 8),
      text: 'Feu',
    );

    test('a non-SOS report is kept (blocked), nothing sent', () async {
      final (c, db, syncs) = await container(quotaPrefs());
      final outcome = await c.read(reportSubmitterProvider)(draft);
      expect(outcome.keptForAccount, isTrue);
      final row = (await db.reportByUuid(outcome.queued.clientUuid))!;
      expect(row.state, ReportState.blocked);
      expect(row.lastError, ApiErrorCode.anonQuotaExhausted.wire);
      expect(row.payload, contains('Feu'));
      expect(syncs, isEmpty);
    });

    test('with reports left the report is queued and sent', () async {
      final (c, db, syncs) = await container(quotaPrefs(remaining: 1));
      final outcome = await c.read(reportSubmitterProvider)(draft);
      expect(outcome.keptForAccount, isFalse);
      final row = (await db.reportByUuid(outcome.queued.clientUuid))!;
      expect(row.state, ReportState.queued);
      expect(syncs, [1]);
    });

    test('a registered account is never gated', () async {
      final (c, db, syncs) = await container({
        ...registeredPrefs(locale: 'en'),
        'quota.anon_limit': 5,
        'quota.anon_remaining': 0,
      }, session: testSession);
      final outcome = await c.read(reportSubmitterProvider)(draft);
      expect(outcome.keptForAccount, isFalse);
      expect(syncs, [1]);
    });

    test('an SOS from the report form is never gated', () async {
      final (c, db, syncs) = await container(quotaPrefs());
      final outcome = await c.read(reportSubmitterProvider)(
        const ReportDraft(
          category: ReportCategory.sos,
          location: GeoPoint(lat: 36.8, lon: 10.18),
        ),
      );
      expect(outcome.keptForAccount, isFalse);
      expect(
        (await db.reportByUuid(outcome.queued.clientUuid))!.state,
        ReportState.queued,
      );
      expect(syncs, [1]);
    });

    testWidgets('the quota screen tells the draft is kept, with its code', (
      tester,
    ) async {
      await pumpApp(tester, prefs: quotaPrefs());
      await go(tester, Routes.quotaFor('TMP-ABC234'));
      expect(find.byKey(const Key('anon-quota-draft-kept')), findsOneWidget);
      expect(find.textContaining('TMP-ABC234'), findsOneWidget);
      await tester.scrollUntilVisible(
        find.byKey(const Key('anon-quota-call-198')),
        200,
      );
      expect(find.byKey(const Key('anon-quota-call-198')), findsOneWidget);
      await unmountApp(tester);
    });

    testWidgets('the SOS button is never gated on the device', (tester) async {
      final h = await pumpApp(tester, prefs: quotaPrefs());
      await tester.longPress(find.byKey(const Key('sos-button')));
      await tester.pumpAndSettle();
      expect(h.sos.calls, 1);
      expect(find.byKey(const Key('anon-quota-draft-kept')), findsNothing);
      await unmountApp(tester);
    });
  });

  test('gate: anonymous non-SOS with 0 left only', () {
    const anon = IdentityState(
      mode: IdentityMode.anonymous,
      role: UserRole.citizen,
    );
    const empty = AnonQuota(limit: 5, remaining: 0);
    expect(
      anonQuotaBlocks(
        identity: anon,
        category: ReportCategory.fire,
        quota: empty,
      ),
      isTrue,
    );
    expect(
      anonQuotaBlocks(
        identity: anon,
        category: ReportCategory.sos,
        quota: empty,
      ),
      isFalse,
    );
    expect(
      anonQuotaBlocks(
        identity: anon,
        category: ReportCategory.fire,
        quota: const AnonQuota(limit: 5, remaining: 1),
      ),
      isFalse,
    );
    expect(
      anonQuotaBlocks(
        identity: anon,
        category: ReportCategory.fire,
        quota: null,
      ),
      isFalse,
    );
    expect(
      anonQuotaBlocks(
        identity: const IdentityState(
          mode: IdentityMode.registered,
          role: UserRole.citizen,
        ),
        category: ReportCategory.fire,
        quota: empty,
      ),
      isFalse,
    );
  });
}
