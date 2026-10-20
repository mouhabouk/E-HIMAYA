import 'dart:convert';

import 'package:ehimaya/core/connectivity/connectivity.dart';
import 'package:ehimaya/core/http/models.dart';
import 'package:ehimaya/core/http/notify_models.dart';
import 'package:ehimaya/core/http/weather_models.dart';
import 'package:ehimaya/core/power/battery_saver.dart';
import 'package:ehimaya/core/power/scheduling.dart';
import 'package:ehimaya/core/storage/app_prefs.dart';
import 'package:ehimaya/features/weather/weather_providers.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/fake_http.dart';
import '../helpers/hardening_fakes.dart';
import '../helpers/phase5_fixtures.dart';
import '../helpers/weather_fixtures.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  final t0 = DateTime.utc(2026, 10, 20, 10, 5);

  group('WeatherReport.fromJson', () {
    test('reads the documented fields', () {
      final r = WeatherReport.fromJson(
        weatherJson(alerts: [weatherAlertJson()]),
      )!;
      expect(r.current.temperatureC, 24.4);
      expect(r.current.windKmh, 18.2);
      expect(r.current.gustKmh, 35);
      expect(r.current.windDirectionDeg, 270);
      expect(r.current.humidityPct, 55);
      expect(r.current.precipitation24hMm, 2.1);
      expect(r.current.fireDanger, FireDanger.high);
      expect(r.current.rainLevel, RainLevel.none);
      expect(r.hourly, hasLength(12));
      expect(r.alerts.single.severity, AlertSeverity.medium);
      expect(r.attribution.text, 'Weather data by Open-Meteo.com (CC BY 4.0)');
      expect(r.attribution.url, 'https://open-meteo.com/');
      expect(r.simulated, isFalse);
      expect(r.point?.lat, 36.75);
    });

    test('accepts aliases, string attribution and skips bad items', () {
      final r = WeatherReport.fromJson({
        'generated_at': '2026-10-20T10:00:00Z',
        'current': {
          'temperature': 30,
          'wind_kmh': 12,
          'wind_gusts_kmh': 40,
          'humidity_pct': 20,
          'rain_1h_mm': 1.5,
          'rain_24h_mm': 60,
          'fire_danger': 'very_high',
          'rain_level': {'level': 'warning'},
        },
        'hourly': [
          {'time': 'not a date'},
          {'time': '2026-10-20T12:00:00Z', 'temperature': 29},
          {'time': '2026-10-20T11:00:00Z', 'temperature': 30},
          'junk',
        ],
        'alerts': [
          {'no': 'id'},
          weatherAlertJson(),
        ],
        'attribution': 'INM Tunisie',
        'simulated': true,
      })!;
      // "current" without its own time takes the answer's time.
      expect(r.current.time, DateTime.utc(2026, 10, 20, 10));
      expect(r.current.temperatureC, 30);
      expect(r.current.gustKmh, 40);
      expect(r.current.precipitationMmH, 1.5);
      expect(r.current.precipitation24hMm, 60);
      expect(r.current.fireDanger, FireDanger.veryHigh);
      expect(r.current.rainLevel, RainLevel.warning);
      // Sorted by time, invalid hours dropped.
      expect(r.hourly.map((h) => h.time.hour), [11, 12]);
      expect(r.alerts, hasLength(1));
      expect(r.attribution.text, 'INM Tunisie');
      expect(r.attribution.url, isNull);
      expect(r.simulated, isTrue);
    });

    test(
      'no attribution: Open-Meteo is credited; no "current": unreadable',
      () {
        final r = WeatherReport.fromJson(weatherJson(attribution: null))!;
        expect(r.attribution.text, contains('Open-Meteo'));
        expect(r.attribution.text, contains('CC BY 4.0'));
        expect(WeatherReport.fromJson({'hourly': []}), isNull);
        expect(WeatherReport.fromJson(['x']), isNull);
        // An http:// link is never opened.
        expect(
          WeatherAttribution.fromJson({'text': 'x', 'url': 'http://e.test'})
              .url,
          isNull,
        );
      },
    );

    test('next hours, badges over the hours shown, alerts in force', () {
      final r = WeatherReport.fromJson(
        weatherJson(
          alerts: [
            weatherAlertJson(id: 'low', severity: 'low'),
            weatherAlertJson(id: 'high', severity: 'high'),
            {
              ...weatherAlertJson(id: 'old'),
              'expires_at': '2026-10-20T09:00:00Z',
            },
          ],
        ),
      )!;
      final now = DateTime.utc(2026, 10, 20, 11, 30);
      final next = r.nextHours(now, count: 4);
      expect(next.map((h) => h.time.hour), [12, 13, 14, 15]);
      // The watch is at 13:00, within the hours shown.
      expect(r.maxRainLevel(now), RainLevel.watch);
      expect(r.maxRainLevel(DateTime.utc(2026, 10, 20, 14)), RainLevel.none);
      expect(r.maxFireDanger(now), FireDanger.high);
      expect(r.activeAlerts(now).map((a) => a.id), ['high', 'low']);
    });
  });

  group('WeatherPolling', () {
    test('at most every 30 min, 60 in battery saver, back-off', () {
      bool due(Duration since, {int failures = 0, bool saver = false}) =>
          WeatherPolling.isDue(
            lastAttempt: t0,
            now: t0.add(since),
            failures: failures,
            batterySaver: saver,
          );
      expect(
        WeatherPolling.isDue(
          lastAttempt: null,
          now: t0,
          failures: 0,
          batterySaver: false,
        ),
        isTrue,
      );
      expect(due(const Duration(minutes: 29)), isFalse);
      expect(due(const Duration(minutes: 30)), isTrue);
      expect(due(const Duration(minutes: 59), saver: true), isFalse);
      expect(due(const Duration(minutes: 60), saver: true), isTrue);
      expect(due(const Duration(minutes: 59), failures: 1), isFalse);
      expect(due(const Duration(minutes: 119), failures: 5), isFalse);
      expect(due(const Duration(minutes: 120), failures: 5), isTrue);
      // Clock moved back: not stuck.
      expect(due(const Duration(minutes: -5)), isTrue);
    });

    test('a manual retry is honoured, but not twice within 15 s', () {
      bool manual(Duration since) => WeatherPolling.isDue(
        lastAttempt: t0,
        now: t0.add(since),
        failures: 3,
        batterySaver: true,
        manual: true,
      );
      expect(manual(const Duration(seconds: 10)), isFalse);
      expect(manual(const Duration(seconds: 15)), isTrue);
    });

    test('coarse point: 2 decimals', () {
      final p = coarseWeatherPoint(
        const GeoPoint(lat: 36.80649, lon: 10.18151, accuracyM: 5),
      );
      expect(p.lat, 36.81);
      expect(p.lon, 10.18);
      expect(p.accuracyM, isNull);
    });
  });

  group('WeatherController', () {
    late DateTime now;
    late ControlledConnectivity net;
    late MovableLocation location;
    late FakeAdapter adapter;
    late int status;
    late bool saver;

    setUp(() {
      now = t0;
      status = 200;
      saver = false;
      net = ControlledConnectivity();
      location = MovableLocation(
        const GeoPoint(lat: 36.80649, lon: 10.18151, accuracyM: 20),
      );
      adapter = FakeAdapter((r) {
        if (r.path != '/api/v1/weather') return const FakeResponse(404);
        return status == 200
            ? FakeResponse(200, json: weatherJson(from: now))
            : FakeResponse(status, json: const {'detail': 'x'});
      });
    });

    int weatherRequests() =>
        adapter.requests.where((r) => r.path == '/api/v1/weather').length;

    Future<ProviderContainer> container({
      Map<String, Object> prefs = const {},
    }) => phase5Container(
      adapter,
      registered: false,
      prefs: prefs,
      clock: () => now,
      location: location,
      overrides: [
        connectivityProvider.overrideWithValue(net),
        batterySaverActiveProvider.overrideWith((ref) => saver),
      ],
    );

    Future<WeatherCardState> shown(ProviderContainer c) async {
      c.read(weatherProvider);
      await pumpEventQueue();
      return c.read(weatherProvider);
    }

    test('first display fetches at the coarse position and caches', () async {
      final c = await container();
      final s = await shown(c);
      expect(weatherRequests(), 1);
      final q = adapter.requests.single.uri.queryParameters;
      expect(q['lat'], '36.81');
      expect(q['lon'], '10.18');
      // Public endpoint: no credentials sent.
      expect(adapter.requests.single.header('authorization'), isNull);
      expect(s.report, isNotNull);
      expect(s.fromCache, isFalse);
      expect(s.issue, isNull);
      expect(s.loading, isFalse);
      final cached = jsonDecode(
        c.read(appPrefsProvider).lastWeatherJson!,
      ) as Map<String, Object?>;
      expect(cached['fetched_at'], t0.toIso8601String());
      expect((cached['report']! as Map)['current'], isNotNull);
    });

    test('never more often than every 30 min (60 in battery saver)', () async {
      final c = await container();
      await shown(c);
      final weather = c.read(weatherProvider.notifier);
      now = t0.add(const Duration(minutes: 29));
      await weather.refreshIfDue();
      expect(weatherRequests(), 1);
      now = t0.add(const Duration(minutes: 30));
      await weather.refreshIfDue();
      expect(weatherRequests(), 2);

      saver = true;
      c.invalidate(batterySaverActiveProvider);
      now = t0.add(const Duration(minutes: 75));
      await weather.refreshIfDue();
      expect(weatherRequests(), 2);
      now = t0.add(const Duration(minutes: 90));
      await weather.refreshIfDue();
      expect(weatherRequests(), 3);
    });

    test('a failure keeps the last values, marked, and backs off', () async {
      final c = await container();
      await shown(c);
      status = 503;
      now = t0.add(const Duration(minutes: 30));
      final weather = c.read(weatherProvider.notifier);
      await weather.refreshIfDue();
      var s = c.read(weatherProvider);
      expect(weatherRequests(), 2);
      expect(s.report, isNotNull);
      expect(s.issue, WeatherIssue.unavailable);
      expect(weather.failures, 1);
      // Back-off: 60 min after a failure.
      now = t0.add(const Duration(minutes: 80));
      await weather.refreshIfDue();
      expect(weatherRequests(), 2);
      // The user's retry goes through.
      status = 200;
      await weather.refreshManually();
      s = c.read(weatherProvider);
      expect(weatherRequests(), 3);
      expect(s.issue, isNull);
      expect(weather.failures, 0);
    });

    test('offline: nothing is asked, and it runs once back online', () async {
      net.online = false;
      final c = await container();
      final s = await shown(c);
      expect(weatherRequests(), 0);
      expect(s.issue, WeatherIssue.offline);
      expect(s.report, isNull);
      net.online = true;
      await c.read(weatherProvider.notifier).refreshIfDue();
      expect(weatherRequests(), 1);
    });

    test('no position or outside Tunisia: nothing is asked', () async {
      location.fix = null;
      final c = await container();
      expect((await shown(c)).issue, WeatherIssue.noLocation);
      expect(c.read(weatherProvider.notifier).lastAttempt, isNull);
      location.fix = const GeoPoint(lat: 48.85, lon: 2.35);
      await c.read(weatherProvider.notifier).refreshManually();
      expect(c.read(weatherProvider).issue, WeatherIssue.outsideCoverage);
      expect(weatherRequests(), 0);
      // Location granted / back home: asked at once.
      location.fix = const GeoPoint(lat: 36.8, lon: 10.18);
      await c.read(weatherProvider.notifier).refreshIfDue();
      expect(weatherRequests(), 1);
      expect(c.read(weatherProvider).issue, isNull);
    });

    test('offline copy is shown with its time and counts as recent', () async {
      final fetched = t0.subtract(const Duration(minutes: 10));
      final c = await container(
        prefs: {
          'weather.last': jsonEncode({
            'fetched_at': fetched.toIso8601String(),
            'report': weatherJson(from: fetched),
          }),
        },
      );
      final s = await shown(c);
      expect(s.report, isNotNull);
      expect(s.fromCache, isTrue);
      expect(s.fetchedAt, fetched);
      expect(weatherRequests(), 0);
    });

    test('a copy older than 24 h is not shown', () async {
      net.online = false;
      final fetched = t0.subtract(const Duration(hours: 25));
      final c = await container(
        prefs: {
          'weather.last': jsonEncode({
            'fetched_at': fetched.toIso8601String(),
            'report': weatherJson(from: fetched),
          }),
        },
      );
      final s = await shown(c);
      expect(s.report, isNull);
      expect(s.issue, WeatherIssue.offline);
    });

    test('weather alerts in force are exposed for the alert detail', () async {
      adapter.handler = (r) => FakeResponse(
        200,
        json: weatherJson(
          from: now,
          alerts: [
            weatherAlertJson(id: 'w1'),
            {
              ...weatherAlertJson(id: 'w0'),
              'expires_at': '2026-10-20T09:00:00Z',
            },
          ],
        ),
      );
      final c = await container();
      await shown(c);
      expect(c.read(weatherAlertsProvider).map((a) => a.id), ['w1']);
    });

    test('account deletion wipes the weather copy', () async {
      final c = await container();
      await shown(c);
      await c.read(appPrefsProvider).wipeForAccountDeletion();
      expect(c.read(appPrefsProvider).lastWeatherJson, isNull);
    });
  });

  group('WeatherScheduler', () {
    late ControlledConnectivity net;
    late FakeAdapter adapter;

    setUp(() {
      net = ControlledConnectivity();
      adapter = FakeAdapter(
        (r) => FakeResponse(200, json: weatherJson(from: DateTime.now())),
      );
    });

    Future<(ProviderContainer, WeatherScheduler)> started() async {
      final c = await phase5Container(
        adapter,
        registered: false,
        location: MovableLocation(const GeoPoint(lat: 36.8, lon: 10.18)),
        overrides: [connectivityProvider.overrideWithValue(net)],
      );
      final s = c.read(weatherSchedulerProvider);
      s.start();
      addTearDown(s.dispose);
      return (c, s);
    }

    test('nothing is asked before the card was shown', () async {
      final (_, s) = await started();
      expect(s.isScheduled, isFalse);
      await pumpEventQueue();
      expect(adapter.requests, isEmpty);
    });

    test(
      'foreground only, never offline; period follows the battery',
      () async {
        final (c, s) = await started();
        c.read(weatherProvider);
        await pumpEventQueue();
        expect(adapter.requests, hasLength(1));
        expect(s.isScheduled, isTrue);
        expect(s.period, const Duration(minutes: 30));

        s.didChangeAppLifecycleState(AppLifecycleState.paused);
        expect(s.isScheduled, isFalse);
        s.didChangeAppLifecycleState(AppLifecycleState.resumed);
        await pumpEventQueue();
        // Resumed within 30 min: rescheduled, no extra request.
        expect(adapter.requests, hasLength(1));
        expect(s.isScheduled, isTrue);

        net.set(false);
        await pumpEventQueue();
        expect(s.isScheduled, isFalse);
        net.set(true);
        await pumpEventQueue();
        expect(s.isScheduled, isTrue);
        expect(adapter.requests, hasLength(1));

        await c
            .read(batterySaverProvider.notifier)
            .setMode(BatterySaverMode.on);
        expect(s.period, const Duration(minutes: 60));
      },
    );
  });
}
