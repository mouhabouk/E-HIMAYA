import 'package:ehimaya/core/config/providers.dart';
import 'package:ehimaya/core/platform/device_services.dart';
import 'package:ehimaya/core/push/push_messaging.dart';
import 'package:ehimaya/features/live/live_controller.dart';
import 'package:ehimaya/features/live/live_publisher.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/app_harness.dart';
import '../helpers/fake_http.dart';
import '../helpers/hardening_fakes.dart';
import '../helpers/live_fakes.dart';
import '../helpers/phase5_fixtures.dart';
import 'phase5_flow_test.dart' show scrollTo;

void main() {
  late FakeLiveServer server;
  late FakeDeviceServices device;
  late List<FakeLivePublisher> publishers;

  /// The app clock, advanced by hand with the fake timers (elapsed time of the indicator).
  var now = DateTime.utc(2026, 10, 19, 10, 15);
  Future<void> advance(WidgetTester tester, Duration d) async {
    now = now.add(d);
    await tester.pump(d);
  }

  setUp(() {
    now = DateTime.utc(2026, 10, 19, 10, 15);
    server = FakeLiveServer();
    device = FakeDeviceServices();
    publishers = [];
  });

  Future<void> pumpLiveApp(
    WidgetTester tester, {
    String locale = 'ar',
    LiveTimings timings = const LiveTimings(),
    FakeHandler? api,
  }) => pumpApp(
    tester,
    prefs: onboardedPrefs(locale: locale),
    api: api ?? server.handle,
    overrides: [
      pushMessagingProvider.overrideWithValue(FakePushMessaging()),
      deviceServicesProvider.overrideWithValue(device),
      liveTimingsProvider.overrideWithValue(timings),
      clockProvider.overrideWithValue(() => now),
      livePublisherFactoryProvider.overrideWithValue(() {
        final p = FakeLivePublisher();
        publishers.add(p);
        return p;
      }),
    ],
  );

  /// A few frames without settling (the LIVE indicator pulses forever).
  Future<void> frames(WidgetTester tester, [int n = 6]) async {
    for (var i = 0; i < n; i++) {
      await tester.pump(const Duration(milliseconds: 100));
    }
  }

  Future<void> openLive(WidgetTester tester) async {
    await scrollTo(tester, 'home-live');
    await tester.tap(find.byKey(const Key('home-live')));
    await tester.pumpAndSettle();
  }

  testWidgets('home Live button: rationale, LIVE indicator, one-tap stop', (
    tester,
  ) async {
    await pumpLiveApp(tester);
    expect(find.text('بث مباشر'), findsWidgets);
    await openLive(tester);

    // Before start: what is shared and why, and the incident type.
    expect(find.byKey(const Key('live-rationale')), findsOneWidget);
    expect(find.textContaining('الكاميرا والميكروفون'), findsOneWidget);
    await tester.tap(find.byKey(const Key('live-category-fire')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('live-start')));
    await frames(tester);

    expect(server.reportsCreated, 1);
    expect(server.whipPosts.single.header('Authorization'), 'Bearer tok-st-1');
    expect(find.byKey(const Key('live-indicator')), findsOneWidget);
    expect(find.text('مباشر'), findsOneWidget);
    expect(find.text('00:00'), findsOneWidget);
    expect(find.byKey(const Key('fake-preview')), findsOneWidget);
    expect(find.byKey(const Key('live-simulation-band')), findsNothing);
    expect(device.screenOn, [true]);

    await advance(tester, const Duration(seconds: 3));
    expect(find.text('00:03'), findsOneWidget);
    expect(server.locations['st-1'], isNotEmpty);

    // Mute and camera switch.
    await tester.tap(find.byKey(const Key('live-mute')));
    await frames(tester, 2);
    expect(publishers.single.muted, isTrue);
    await tester.tap(find.byKey(const Key('live-switch-camera')));
    await frames(tester, 2);
    expect(publishers.single.front, isTrue);

    // One tap.
    await tester.tap(find.byKey(const Key('live-stop')));
    await frames(tester);
    expect(server.stops, ['st-1']);
    expect(server.whipDeletes, hasLength(1));
    expect(find.byKey(const Key('live-ended')), findsOneWidget);
    expect(find.text('أوقفت البث. التسجيل محفوظ مع بلاغك.'), findsOneWidget);
    expect(device.screenOn.last, isFalse);
    expect(publishers.single.disposed, isTrue);

    await tester.tap(find.byKey(const Key('live-done')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('home-live')), findsOneWidget);
    await unmountApp(tester);
  });

  testWidgets('simulated stream: amber band and EN DIRECT in French', (
    tester,
  ) async {
    server.simulated = true;
    await pumpLiveApp(tester, locale: 'fr');
    await openLive(tester);
    await tester.tap(find.byKey(const Key('live-start')));
    await frames(tester);
    expect(find.text('EN DIRECT'), findsOneWidget);
    expect(find.byKey(const Key('live-simulation-band')), findsOneWidget);
    expect(find.textContaining('Mode simulation'), findsOneWidget);

    // The operator ends it from the dashboard.
    server.operatorStops('st-1');
    await advance(tester, const Duration(seconds: 10));
    await frames(tester);
    expect(find.byKey(const Key('live-ended')), findsOneWidget);
    expect(
      find.text(
        'L’opérateur a mis fin au direct. Merci, les images sont bien arrivées.',
      ),
      findsOneWidget,
    );
    // The band stays on the summary of a simulated stream.
    expect(find.byKey(const Key('live-simulation-band')), findsOneWidget);
    await unmountApp(tester);
  });

  testWidgets('English LIVE label, and a failure offers the clip fallback', (
    tester,
  ) async {
    server.reportsOffline = true;
    await pumpLiveApp(
      tester,
      locale: 'en',
      timings: const LiveTimings(reportWait: Duration.zero),
    );
    await openLive(tester);
    await tester.tap(find.byKey(const Key('live-start')));
    await frames(tester);
    expect(find.byKey(const Key('live-failed')), findsOneWidget);
    expect(find.textContaining('saved on the phone'), findsOneWidget);
    expect(find.byKey(const Key('live-record-clip')), findsOneWidget);
    expect(find.text('Record a clip (60 s)'), findsOneWidget);
    expect(find.byKey(const Key('live-retry')), findsOneWidget);
    expect(device.screenOn.last, isFalse);

    // Retry reuses the report already queued (no second report).
    server.reportsOffline = false;
    await tester.tap(find.byKey(const Key('live-retry')));
    await frames(tester);
    expect(server.reportsCreated, 1);
    expect(find.text('LIVE'), findsOneWidget);
    await tester.tap(find.byKey(const Key('live-stop')));
    await frames(tester);
    await unmountApp(tester);
  });

  testWidgets('camera refused: settings shortcut, no clip offer', (
    tester,
  ) async {
    await pumpApp(
      tester,
      prefs: onboardedPrefs(locale: 'en'),
      api: server.handle,
      overrides: [
        pushMessagingProvider.overrideWithValue(FakePushMessaging()),
        deviceServicesProvider.overrideWithValue(device),
        livePublisherFactoryProvider.overrideWithValue(
          () => FakeLivePublisher()..openError = const MediaPermissionDenied(),
        ),
      ],
    );
    await openLive(tester);
    await tester.tap(find.byKey(const Key('live-start')));
    await frames(tester);
    expect(
      find.textContaining('Camera or microphone access was refused'),
      findsOneWidget,
    );
    expect(find.byKey(const Key('live-record-clip')), findsNothing);
    await tester.tap(find.byKey(const Key('live-open-settings')));
    await frames(tester, 2);
    expect(device.opened, contains('app-settings'));
    expect(server.reportsCreated, 0);
    await unmountApp(tester);
  });

  testWidgets('a report of My reports can go live', (tester) async {
    await pumpLiveApp(
      tester,
      locale: 'en',
      api: (r) {
        if (r.path == '/api/v1/reports/mine') {
          return const FakeResponse(
            200,
            json: {
              'items': [
                {
                  'id': 'rep-9',
                  'tracking_code': 'EH-26-11-0000009',
                  'client_uuid': 'c-9',
                  'category': 'fire',
                  'status': 'in_progress',
                  'created_at': '2026-10-19T10:00:00Z',
                  'media': [],
                },
                {
                  'id': 'rep-8',
                  'tracking_code': 'EH-26-11-0000008',
                  'client_uuid': 'c-8',
                  'category': 'flood',
                  'status': 'closed',
                  'created_at': '2026-10-18T10:00:00Z',
                  'media': [],
                },
              ],
              'next_before': null,
            },
          );
        }
        return server.handle(r);
      },
    );
    await tester.tap(find.text('My reports').last);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('go-live-EH-26-11-0000009')), findsOneWidget);
    // A closed report cannot.
    expect(find.byKey(const Key('go-live-EH-26-11-0000008')), findsNothing);
    await tester.tap(find.byKey(const Key('go-live-EH-26-11-0000009')));
    await tester.pumpAndSettle();
    expect(find.text('Report EH-26-11-0000009'), findsOneWidget);
    // No incident type to choose for an existing report.
    expect(find.byKey(const Key('live-category-fire')), findsNothing);
    await tester.tap(find.byKey(const Key('live-start')));
    await frames(tester);
    expect(server.reportsCreated, 0);
    expect(server.created, ['st-1']);
    expect(find.text('LIVE'), findsOneWidget);

    // Leaving with the back button asks first, then stops.
    final dynamic navigator = tester.state(find.byType(Navigator).last);
    await navigator.maybePop();
    await frames(tester, 3);
    expect(find.text('Stop the live stream?'), findsOneWidget);
    await tester.tap(find.widgetWithText(FilledButton, 'Stop live'));
    await frames(tester);
    expect(server.stops, ['st-1']);
    await unmountApp(tester);
  });
}
