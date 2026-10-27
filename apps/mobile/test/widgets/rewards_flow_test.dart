import 'dart:io';

import 'package:ehimaya/core/connectivity/connectivity.dart';
import 'package:ehimaya/core/power/scheduling.dart' show NetworkKind;
import 'package:ehimaya/core/storage/secure_store.dart';
import 'package:ehimaya/features/reports/track_screen.dart';
import 'package:ehimaya/features/rewards/rewards_providers.dart';
import 'package:ehimaya/features/rewards/rewards_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/app_harness.dart';
import '../helpers/fake_http.dart';
import '../helpers/rewards_fixtures.dart';

class _Offline implements ConnectivityMonitor {
  @override
  Future<bool> isOnline() async => false;
  @override
  Stream<bool> get onlineChanges => const Stream.empty();
  @override
  Future<NetworkKind> networkKind() async => NetworkKind.none;
}

const _code = 'EH-26-11-0000042';

FakeHandler rewardsApi({
  Map<String, Object?>? rewards,
  List<String>? pdfAuth,
}) => (r) {
  switch (r.path) {
    case '/api/v1/me/rewards':
      return FakeResponse(200, json: rewards ?? rewardsJson());
    case '/api/v1/me/rewards/certificates/c-1':
      // Redirect to a short-lived presigned storage URL.
      pdfAuth?.add('api:${r.header('authorization')}');
      return const FakeResponse(
        302,
        headers: {
          'location':
              'https://storage.example/certificates/c-1.pdf?X-Amz-Signature=s',
        },
      );
    case '/certificates/c-1.pdf':
      pdfAuth?.add(
        'storage:${r.uri.host}:${r.header('authorization')}:'
        '${r.header('x-device-key')}',
      );
      return const FakeResponse(
        200,
        bytes: fakePdf,
        headers: {'content-type': 'application/pdf'},
      );
    case '/api/v1/me/rewards/history':
      return FakeResponse(
        200,
        json: {
          'items': [
            {
              'id': 3,
              'delta': -50,
              'reason': 'revocation',
              'created_at': '2026-09-02T10:00:00Z',
            },
          ],
          'next_cursor': null,
        },
      );
    case '/api/v1/reports/track/$_code':
      return const FakeResponse(
        200,
        json: {
          'tracking_code': _code,
          'status': 'closed',
          'received_at': '2026-10-17T10:00:00Z',
          'history': [
            {'status': 'received', 'at': '2026-10-17T10:00:00Z'},
            {'status': 'closed', 'at': '2026-10-18T10:00:00Z'},
          ],
        },
      );
  }
  return defaultApiResponse(r);
};

void main() {
  Future<void> tallScreen(WidgetTester tester) async {
    await tester.binding.setSurfaceSize(const Size(800, 3000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
  }

  Future<void> openRewards(WidgetTester tester) async {
    await tester.tap(find.byKey(const Key('home-rewards')));
    await tester.pumpAndSettle();
    expect(find.byType(RewardsScreen), findsOneWidget);
  }

  testWidgets('balance, badge progress, history and safety notice (fr)', (
    tester,
  ) async {
    await tallScreen(tester);
    final h = await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'fr'),
      session: testSession,
      api: rewardsApi(rewards: rewardsJson(historyNextCursor: 'next-1')),
    );
    await openRewards(tester);

    expect(find.text('320'), findsOneWidget);
    expect(find.text('Badge actuel : Bronze'), findsOneWidget);
    expect(
      find.text('Prochain badge, Argent : encore 180 points'),
      findsOneWidget,
    );
    final bar = tester.widget<LinearProgressIndicator>(
      find.byKey(const Key('rewards-progress')),
    );
    expect(bar.value, closeTo(0.64, 1e-9));
    expect(find.text('Bonne catégorie choisie'), findsOneWidget);
    expect(find.text('Signalement vérifié'), findsOneWidget);
    expect(find.text('+25'), findsOneWidget);
    expect(find.text('+50'), findsOneWidget);
    expect(find.textContaining('plafond journalier atteint'), findsOneWidget);
    expect(find.text('Citoyen vigilant'), findsOneWidget);
    expect(find.byKey(const Key('rewards-paused')), findsNothing);
    expect(find.byKey(const Key('rewards-offline')), findsNothing);
    // Fixed safety notice, 198 one tap away, and no cash promised.
    expect(
      find.textContaining('Ne vous mettez jamais en danger'),
      findsOneWidget,
    );
    expect(
      find.textContaining('décision de l’autorité compétente'),
      findsOneWidget,
    );
    await tester.tap(find.byKey(const Key('rewards-call-198')));
    await tester.pumpAndSettle();
    expect(h.dialled, [Uri(scheme: 'tel', path: '198')]);

    // Older history page.
    await tester.tap(find.byKey(const Key('rewards-history-more')));
    await tester.pumpAndSettle();
    expect(find.text('Points retirés'), findsOneWidget);
    expect(find.text('-50'), findsOneWidget);
    expect(find.byKey(const Key('rewards-history-more')), findsNothing);
    final more = h.adapter.requests.singleWhere(
      (r) => r.path == '/api/v1/me/rewards/history',
    );
    expect(more.uri.queryParameters['cursor'], 'next-1');
    // Bearer, never the device key.
    final summary = h.adapter.requests.firstWhere(
      (r) => r.path == '/api/v1/me/rewards',
    );
    expect(summary.header('authorization'), 'Bearer a.b.c');
    expect(summary.header('x-device-key'), isNull);
    await unmountApp(tester);
  });

  testWidgets('a certificate is downloaded and opened as PDF', (tester) async {
    await tallScreen(tester);
    final dir = Directory.systemTemp.createTempSync('ehimaya-cert');
    addTearDown(() => dir.deleteSync(recursive: true));
    final opened = <(String, String)>[];
    final auth = <String>[];
    await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'en'),
      session: testSession,
      api: rewardsApi(pdfAuth: auth),
      overrides: [
        certificateDirProvider.overrideWithValue(() async => dir),
        fileOpenerProvider.overrideWithValue((path, type) async {
          opened.add((path, type));
          return true;
        }),
      ],
    );
    await openRewards(tester);
    expect(find.text('Vigilant citizen'), findsOneWidget);
    await tester.runAsync(() async {
      await tester.tap(find.byKey(const Key('rewards-certificate-c-1')));
      for (var i = 0; i < 50 && opened.isEmpty; i++) {
        await Future<void>.delayed(const Duration(milliseconds: 20));
      }
    });
    await tester.pumpAndSettle();
    // The Bearer token goes to the API only, never to the storage URL.
    expect(auth, ['api:Bearer a.b.c', 'storage:storage.example:null:null']);
    expect(opened, hasLength(1));
    expect(opened.single.$2, 'application/pdf');
    expect(opened.single.$1, endsWith('ehimaya-certificate-c-1.pdf'));
    expect(File(opened.single.$1).readAsBytesSync(), fakePdf);
    await unmountApp(tester);
  });

  testWidgets('paused at disaster level: notice with the queued points', (
    tester,
  ) async {
    await tallScreen(tester);
    await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'en'),
      session: testSession,
      api: rewardsApi(rewards: rewardsJson(paused: true, pendingPoints: 40)),
    );
    await openRewards(tester);
    expect(find.byKey(const Key('rewards-paused')), findsOneWidget);
    expect(find.text('Points paused'), findsOneWidget);
    expect(find.textContaining('Points waiting: 40'), findsOneWidget);
    await unmountApp(tester);
  });

  testWidgets('anonymous users see why they earn no points', (tester) async {
    await tallScreen(tester);
    final h = await pumpApp(
      tester,
      prefs: onboardedPrefs(locale: 'en'),
      api: rewardsApi(),
    );
    await openRewards(tester);
    expect(find.byKey(const Key('rewards-anonymous')), findsOneWidget);
    expect(find.text('Anonymous reports earn no points'), findsOneWidget);
    expect(find.byKey(const Key('rewards-register')), findsOneWidget);
    expect(find.byKey(const Key('rewards-safety')), findsOneWidget);
    expect(find.byKey(const Key('rewards-balance')), findsNothing);
    expect(
      h.adapter.requests.where((r) => r.path.startsWith('/api/v1/me/rewards')),
      isEmpty,
    );
    await unmountApp(tester);
  });

  testWidgets('offline: the last copy is shown with its date', (tester) async {
    await tallScreen(tester);
    final secure = MemorySecureStore();
    await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'en'),
      session: testSession,
      secure: secure,
      api: rewardsApi(rewards: rewardsJson(balance: 640)),
    );
    await openRewards(tester);
    expect(find.text('640'), findsOneWidget);
    expect(secure.values[SecureStoreKeys.rewardsCache], isNotNull);
    await unmountApp(tester);

    final h = await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'en'),
      session: testSession,
      secure: secure,
      connectivity: _Offline(),
      api: (_) => const FakeResponse.network(),
    );
    await openRewards(tester);
    expect(find.text('640'), findsOneWidget);
    expect(find.byKey(const Key('rewards-offline')), findsOneWidget);
    expect(find.textContaining('Offline: copy saved on'), findsOneWidget);
    expect(
      h.adapter.requests.where((r) => r.path == '/api/v1/me/rewards'),
      isEmpty,
    );
    await unmountApp(tester);
  });

  testWidgets('offline without a copy: error and retry', (tester) async {
    await tallScreen(tester);
    await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'en'),
      session: testSession,
      connectivity: _Offline(),
      api: (_) => const FakeResponse.network(),
    );
    await openRewards(tester);
    expect(find.byKey(const Key('rewards-error')), findsOneWidget);
    expect(find.byKey(const Key('rewards-safety')), findsOneWidget);
    await unmountApp(tester);
  });

  testWidgets('Arabic: right to left, numbers stay left to right', (
    tester,
  ) async {
    await tallScreen(tester);
    await pumpApp(
      tester,
      prefs: registeredPrefs(),
      session: testSession,
      api: rewardsApi(),
    );
    await openRewards(tester);
    expect(find.text('مكافآتي'), findsWidgets);
    expect(
      Directionality.of(tester.element(find.byType(RewardsScreen))),
      TextDirection.rtl,
    );
    final balance = tester.widget<Text>(
      find.byKey(const Key('rewards-balance')),
    );
    expect(balance.textDirection, TextDirection.ltr);
    expect(find.textContaining('لا تعرّض نفسك أبدا للخطر'), findsOneWidget);
    await unmountApp(tester);
  });

  group('tracking screen', () {
    Future<void> track(WidgetTester tester) async {
      await tester.tap(find.byKey(const Key('home-track')));
      await tester.pumpAndSettle();
      expect(find.byType(TrackScreen), findsOneWidget);
      await tester.enterText(find.byKey(const Key('track-field')), _code);
      await tester.tap(find.byIcon(Icons.search));
      await tester.pumpAndSettle();
    }

    testWidgets('shows the points the report earned', (tester) async {
      await tallScreen(tester);
      await pumpApp(
        tester,
        prefs: registeredPrefs(locale: 'en'),
        session: testSession,
        api: rewardsApi(),
      );
      await track(tester);
      expect(find.byKey(const Key('track-points')), findsOneWidget);
      expect(find.text('Points earned by this report: 75'), findsOneWidget);
      await tester.tap(find.text('See my rewards'));
      await tester.pumpAndSettle();
      expect(find.byType(RewardsScreen), findsOneWidget);
      await unmountApp(tester);
    });

    testWidgets('the team on its way, then there (F-APP-38)', (tester) async {
      await tallScreen(tester);
      final base = rewardsApi();
      await pumpApp(
        tester,
        prefs: onboardedPrefs(locale: 'en'),
        api: (r) => r.path == '/api/v1/reports/track/$_code'
            ? const FakeResponse(
                200,
                json: {
                  'tracking_code': _code,
                  'status': 'in_progress',
                  'received_at': '2026-10-17T10:00:00Z',
                  'team_en_route_at': '2026-10-17T10:04:00Z',
                  'team_on_scene_at': '2026-10-17T10:12:00Z',
                  'history': [],
                },
              )
            : base(r),
      );
      await track(tester);
      expect(find.byKey(const Key('track-team')), findsOneWidget);
      expect(find.text('The team has arrived'), findsOneWidget);
      await unmountApp(tester);
    });

    testWidgets('nothing for a report without points', (tester) async {
      await tallScreen(tester);
      await pumpApp(
        tester,
        prefs: registeredPrefs(locale: 'en'),
        session: testSession,
        api: rewardsApi(rewards: rewardsJson()..['history'] = <Object?>[]),
      );
      await track(tester);
      expect(find.text(_code), findsWidgets);
      expect(find.byKey(const Key('track-points')), findsNothing);
      await unmountApp(tester);
    });

    testWidgets('anonymous: no points and no rewards request', (tester) async {
      await tallScreen(tester);
      final h = await pumpApp(
        tester,
        prefs: onboardedPrefs(locale: 'en'),
        api: rewardsApi(),
      );
      await track(tester);
      expect(find.text(_code), findsWidgets);
      expect(find.byKey(const Key('track-points')), findsNothing);
      expect(
        h.adapter.requests.where((r) => r.path == '/api/v1/me/rewards'),
        isEmpty,
      );
      await unmountApp(tester);
    });
  });
}
