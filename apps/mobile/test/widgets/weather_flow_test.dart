import 'dart:async';
import 'dart:convert';

import 'package:drift/drift.dart' show Value;
import 'package:ehimaya/core/config/app_config.dart';
import 'package:ehimaya/core/config/providers.dart';
import 'package:ehimaya/core/db/app_database.dart';
import 'package:ehimaya/core/http/models.dart';
import 'package:ehimaya/core/push/push_messaging.dart';
import 'package:ehimaya/core/routing/app_router.dart';
import 'package:ehimaya/features/home/home_screen.dart';
import 'package:ehimaya/features/report/sms_fallback.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart' show DateFormat;

import '../helpers/app_harness.dart';
import '../helpers/fake_http.dart';
import '../helpers/hardening_fakes.dart';
import '../helpers/phase5_fixtures.dart';
import '../helpers/weather_fixtures.dart';

Future<void> tallScreen(WidgetTester tester) async {
  await tester.binding.setSurfaceSize(const Size(800, 3000));
  addTearDown(() => tester.binding.setSurfaceSize(null));
}

void main() {
  final noPush = pushMessagingProvider.overrideWithValue(FakePushMessaging());
  const tunis = GeoPoint(lat: 36.8065, lon: 10.1815, accuracyM: 12);

  FakeHandler weatherApi(Map<String, Object?> Function() weather) =>
      (r) => r.path == '/api/v1/weather'
      ? FakeResponse(200, json: weather())
      : defaultApiResponse(r);

  int weatherCalls(AppHarness h) =>
      h.adapter.requests.where((r) => r.path == '/api/v1/weather').length;

  group('weather card (FR-A-034)', () {
    testWidgets('values, badges, attribution; a weather alert opens', (
      tester,
    ) async {
      await tallScreen(tester);
      final opened = <Uri>[];
      final h = await pumpApp(
        tester,
        prefs: onboardedPrefs(locale: 'fr'),
        location: MovableLocation(tunis),
        opened: opened,
        overrides: [noPush],
        api: weatherApi(
          () => weatherJson(
            from: DateTime.now().toUtc(),
            alerts: [weatherAlertJson(id: 'w1', severity: 'medium')],
          ),
        ),
      );
      final card = find.byKey(const Key('weather-card'));
      expect(card, findsOneWidget);
      expect(weatherCalls(h), 1);
      // Coarse position only.
      final q = h.adapter.requests
          .firstWhere((r) => r.path == '/api/v1/weather')
          .uri
          .queryParameters;
      expect((q['lat'], q['lon']), ('36.81', '10.18'));

      expect(find.byKey(const Key('weather-temp')), findsOneWidget);
      expect(find.text('Danger d’incendie : élevé'), findsOneWidget);
      expect(find.text('Fortes pluies : vigilance'), findsOneWidget);
      expect(find.textContaining('Vent 18 km/h'), findsOneWidget);
      expect(
        find.text('Données : Weather data by Open-Meteo.com (CC BY 4.0)'),
        findsOneWidget,
      );
      expect(
        tester.widget<Text>(find.byKey(const Key('weather-time'))).data,
        startsWith('Mise à jour'),
      );
      expect(find.byKey(const Key('weather-simulation-band')), findsNothing);
      expect(find.text('Alertes météo en vigueur'), findsOneWidget);

      await tester.tap(find.byKey(const Key('weather-attribution')));
      expect(opened, [Uri.parse('https://open-meteo.com/')]);

      await tester.tap(find.byKey(const Key('weather-alert-w1')));
      await tester.pumpAndSettle();
      expect(find.text('Évitez les oueds'), findsOneWidget);
      await unmountApp(tester);
    });

    testWidgets('Arabic: RTL, next hours read right to left, simulated band', (
      tester,
    ) async {
      await tallScreen(tester);
      final start = DateTime.now().toUtc();
      await pumpApp(
        tester,
        prefs: onboardedPrefs(),
        location: MovableLocation(tunis),
        overrides: [noPush],
        api: weatherApi(() => weatherJson(from: start, simulated: true)),
      );
      final band = find.byKey(const Key('weather-simulation-band'));
      expect(band, findsOneWidget);
      expect(
        find.descendant(
          of: band,
          matching: find.textContaining('وضع المحاكاة'),
        ),
        findsOneWidget,
      );
      expect(find.text('الطقس قربك'), findsOneWidget);
      expect(
        Directionality.of(tester.element(find.text('الطقس قربك'))),
        TextDirection.rtl,
      );
      String hour(int i) =>
          DateFormat.Hm('ar').format(start.add(Duration(hours: i)).toLocal());
      final first = tester.getCenter(find.text(hour(1)));
      final second = tester.getCenter(find.text(hour(2)));
      expect(first.dx, greaterThan(second.dx));
      // Each hour is announced as one sentence.
      final handle = tester.ensureSemantics();
      expect(
        find.bySemanticsLabel(RegExp('^${RegExp.escape(hour(1))}, ')),
        findsOneWidget,
      );
      handle.dispose();
      await unmountApp(tester);
    });

    testWidgets('offline: the copy is shown with its time, nothing asked', (
      tester,
    ) async {
      await tallScreen(tester);
      final fetched = DateTime.now().toUtc().subtract(const Duration(hours: 2));
      final h = await pumpApp(
        tester,
        prefs: {
          ...onboardedPrefs(locale: 'en'),
          'weather.last': jsonEncode({
            'fetched_at': fetched.toIso8601String(),
            'report': weatherJson(from: fetched),
          }),
        },
        location: MovableLocation(tunis),
        connectivity: ControlledConnectivity(online: false),
        overrides: [noPush],
        api: weatherApi(() => weatherJson()),
      );
      expect(weatherCalls(h), 0);
      expect(find.byKey(const Key('weather-temp')), findsOneWidget);
      expect(
        tester.widget<Text>(find.byKey(const Key('weather-time'))).data,
        startsWith('Offline copy from'),
      );
      expect(find.byIcon(Icons.cloud_off), findsOneWidget);
      await unmountApp(tester);
    });

    testWidgets('no position: asks for it only when the user taps', (
      tester,
    ) async {
      await tallScreen(tester);
      final location = MovableLocation(null);
      final h = await pumpApp(
        tester,
        prefs: onboardedPrefs(locale: 'en'),
        location: location,
        overrides: [noPush],
        api: weatherApi(() => weatherJson(from: DateTime.now().toUtc())),
      );
      expect(
        find.text('Allow location access to see the weather where you are.'),
        findsOneWidget,
      );
      expect(weatherCalls(h), 0);
      location.fix = tunis;
      await tester.tap(find.byKey(const Key('weather-use-location')));
      await tester.pumpAndSettle();
      expect(weatherCalls(h), 1);
      expect(find.byKey(const Key('weather-temp')), findsOneWidget);
      await unmountApp(tester);
    });

    testWidgets('server error: message and retry', (tester) async {
      await tallScreen(tester);
      var fail = true;
      var now = DateTime.now();
      final h = await pumpApp(
        tester,
        prefs: onboardedPrefs(locale: 'en'),
        location: MovableLocation(tunis),
        overrides: [noPush, clockProvider.overrideWithValue(() => now)],
        api: (r) => r.path == '/api/v1/weather'
            ? (fail
                  ? const FakeResponse(503, json: {'detail': 'x'})
                  : FakeResponse(200, json: weatherJson(from: now.toUtc())))
            : defaultApiResponse(r),
      );
      expect(find.text('The weather could not be loaded.'), findsOneWidget);
      expect(weatherCalls(h), 1);
      fail = false;
      // A tap right after the failure is not sent (no hammering).
      await tester.tap(find.byKey(const Key('weather-retry')));
      await tester.pumpAndSettle();
      expect(weatherCalls(h), 1);
      now = now.add(const Duration(seconds: 20));
      await tester.tap(find.byKey(const Key('weather-retry')));
      await tester.pumpAndSettle();
      expect(weatherCalls(h), 2);
      expect(find.byKey(const Key('weather-temp')), findsOneWidget);
      await unmountApp(tester);
    });
  });

  group('no-internet fallback (FR-A-048)', () {
    const uuid = '3f2a9c1d-7b4e-4c1a-9d2e-0123456789ab';
    const smsConfig = AppConfig(
      apiBaseUrl: 'http://api.test',
      tusUrl: 'http://tus.test/api/v1/uploads/',
      oidcIssuer: 'http://kc.test/realms/ehimaya-public',
      oidcClientId: 'ehimaya-mobile',
      oidcRedirectUrl: 'tn.ehimaya.app:/oauth2redirect',
      mapTileUrl: 'http://tiles.test/{z}/{x}/{y}.png',
      mapAttribution: 'test',
      portalUrl: 'http://localhost:5174',
      smsReportNumber: '+216 71 000 000',
    );

    Future<void> queueReport(AppHarness h, {String category = 'fire'}) async {
      final now = DateTime.now().toUtc();
      await h.db.insertReport(
        PendingReportsCompanion.insert(
          clientUuid: uuid,
          category: category,
          payload: jsonEncode({
            'client_uuid': uuid,
            'category': category,
            'location': {'lat': 36.8065, 'lon': 10.1815, 'accuracy_m': 11.2},
            'created_at': now.toIso8601String(),
          }),
          tempCode: 'TMP-ABCDEF',
          createdAt: now,
          updatedAt: now,
          state: const Value(ReportState.queued),
        ),
        const [],
      );
    }

    Future<void> openQueued(WidgetTester tester, {bool sos = false}) async {
      unawaited(
        GoRouter.of(tester.element(find.byType(HomeScreen))).push(
          Uri(
            path: Routes.reportQueued,
            queryParameters: {'code': 'TMP-ABCDEF', 'sos': ?(sos ? '1' : null)},
          ).toString(),
        ),
      );
      await tester.pumpAndSettle();
    }

    testWidgets('offline: SMS prepared in the SMS app, 198, fee notice', (
      tester,
    ) async {
      await tallScreen(tester);
      final sms = <Uri>[];
      final h = await pumpApp(
        tester,
        prefs: onboardedPrefs(locale: 'fr'),
        connectivity: ControlledConnectivity(online: false),
        overrides: [
          noPush,
          appConfigProvider.overrideWithValue(smsConfig),
          smsComposerProvider.overrideWithValue((uri) async {
            sms.add(uri);
            return true;
          }),
        ],
      );
      await queueReport(h);
      await openQueued(tester);
      expect(find.byKey(const Key('offline-fallback')), findsOneWidget);
      expect(find.text('Pas de connexion internet'), findsOneWidget);
      expect(find.byKey(const Key('offline-sms-fee')), findsOneWidget);

      await tester.tap(find.byKey(const Key('offline-send-sms')));
      await tester.pumpAndSettle();
      expect(sms, hasLength(1));
      expect(sms.single.scheme, 'sms');
      expect(sms.single.path, '+21671000000');
      expect(
        sms.single.queryParameters['body'],
        'EH1 fire 36.80650,10.18150 12m 3f2a9c1d',
      );

      await tester.tap(find.byKey(const Key('offline-call-198')));
      expect(h.dialled, [Uri(scheme: 'tel', path: '198')]);

      // Still queued: it syncs when the network is back.
      expect((await h.db.reportByUuid(uuid))!.state, ReportState.queued);
      await unmountApp(tester);
    });

    testWidgets('the card goes away when the network comes back', (
      tester,
    ) async {
      await tallScreen(tester);
      final net = ControlledConnectivity(online: false);
      final h = await pumpApp(
        tester,
        prefs: onboardedPrefs(locale: 'en'),
        connectivity: net,
        overrides: [noPush, appConfigProvider.overrideWithValue(smsConfig)],
      );
      await queueReport(h);
      await openQueued(tester);
      expect(find.byKey(const Key('offline-fallback')), findsOneWidget);
      net.set(true);
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('offline-fallback')), findsNothing);
      await unmountApp(tester);
    });

    testWidgets('no SMS number configured: 198 only; SOS shows one call', (
      tester,
    ) async {
      await tallScreen(tester);
      final h = await pumpApp(
        tester,
        prefs: onboardedPrefs(locale: 'en'),
        connectivity: ControlledConnectivity(online: false),
        overrides: [noPush],
      );
      await queueReport(h, category: 'sos');
      await openQueued(tester, sos: true);
      expect(find.byKey(const Key('offline-fallback')), findsOneWidget);
      expect(find.byKey(const Key('offline-send-sms')), findsNothing);
      expect(find.byKey(const Key('offline-sms-fee')), findsNothing);
      expect(find.text('Call 198'), findsOneWidget);
      await unmountApp(tester);
    });

    testWidgets('online: no fallback card', (tester) async {
      await tallScreen(tester);
      final h = await pumpApp(
        tester,
        prefs: onboardedPrefs(locale: 'en'),
        overrides: [noPush, appConfigProvider.overrideWithValue(smsConfig)],
      );
      await queueReport(h);
      await openQueued(tester);
      expect(find.byKey(const Key('queued-code')), findsOneWidget);
      expect(find.byKey(const Key('offline-fallback')), findsNothing);
      await unmountApp(tester);
    });
  });
}
