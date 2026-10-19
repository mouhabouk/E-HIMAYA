import 'package:ehimaya/core/http/api_client.dart' show IdentityInterceptor;
import 'package:ehimaya/core/push/push_messaging.dart';
import 'package:ehimaya/core/push/push_notifications.dart';
import 'package:ehimaya/core/push/push_payload.dart';
import 'package:ehimaya/core/push/push_simulation_banner.dart';
import 'package:ehimaya/core/push/simulated_push_messaging.dart';
import 'package:ehimaya/core/storage/app_prefs.dart';
import 'package:ehimaya/l10n/app_localizations.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../helpers/fake_http.dart';

const _names = PushChannelNames(
  alerts: 'Alerts',
  alertsDescription: 'a',
  general: 'General',
  generalDescription: 'g',
);

class _Shown {
  _Shown(this.id, this.payload, this.channelId);
  final int id;
  final PushPayload payload;
  final String? channelId;
}

class FakeNotifications implements PushNotifications {
  final shown = <_Shown>[];
  void Function(PushPayload)? onTap;
  PushPayload? launch;
  bool failInit = false;

  @override
  Future<PushPayload?> init(
    PushChannelNames names, {
    required void Function(PushPayload payload) onTap,
  }) async {
    if (failInit) throw StateError('no plugin');
    this.onTap = onTap;
    return launch;
  }

  @override
  Future<void> requestPermission() async {}

  @override
  Future<void> show(int id, PushPayload payload, {String? channelId}) async =>
      shown.add(_Shown(id, payload, channelId));
}

Map<String, Object?> _item(
  int seq, {
  Object? data = const {'type': 'alert', 'id': 'a-1'},
  String? channel = 'ehimaya_alerts',
  String? title = 'Flood warning',
}) => {
  'seq': seq,
  'id': 'm$seq',
  'channel': 'push',
  'received_at': '2026-10-19T10:00:00Z',
  'token': 'sim-x',
  'to': null,
  'title': title,
  'body': 'Move to higher ground',
  'text': null,
  'data': data,
  'android_channel': channel,
  'priority': 'high',
  'segments': null,
  'encoding': null,
};

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late AppPrefs prefs;
  late FakeAdapter adapter;
  late FakeNotifications notifications;
  late List<Map<String, Object?>> inbox;

  SimulatedPushMessaging build({Duration? interval}) {
    final sim = SimulatedPushMessaging(
      dio: buildSimulatorDio('http://sim.test:8090', adapter: adapter),
      prefs: prefs,
      notifications: notifications,
      interval: interval ?? const Duration(hours: 1),
    );
    addTearDown(sim.dispose);
    return sim;
  }

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    prefs = AppPrefs(await SharedPreferences.getInstance());
    notifications = FakeNotifications();
    inbox = [];
    adapter = FakeAdapter((r) {
      final after = int.parse(r.uri.queryParameters['after'] ?? '0');
      final items = [
        for (final i in inbox)
          if ((i['seq'] as int) > after) i,
      ];
      return FakeResponse(
        200,
        json: {
          'items': items,
          'last_seq': inbox.isEmpty ? 0 : inbox.last['seq'],
        },
      );
    });
  });

  test('token is sim-<uuid v4>, persisted and reused after restart', () async {
    final first = await build().token();
    expect(
      first,
      matches(
        RegExp(
          r'^sim-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
        ),
      ),
    );
    expect(prefs.simPushToken, first);
    expect(await build().token(), first);
  });

  test('polls without identity headers, with after = last seq', () async {
    final sim = build();
    final token = await sim.token();
    inbox.add(_item(3));
    expect(await sim.pollOnce(), isTrue);
    inbox.add(_item(7, data: {'type': 'info', 'id': 'n-1'}, channel: null));
    expect(await sim.pollOnce(), isTrue);

    final first = adapter.requests.first;
    expect(first.path, '/api/messages');
    expect(first.uri.host, 'sim.test');
    expect(first.uri.queryParameters, {
      'channel': 'push',
      'token': token,
      'after': '0',
      'limit': '50',
    });
    expect(first.header('Authorization'), isNull);
    expect(first.header('X-Device-Key'), isNull);
    expect(adapter.requests[1].uri.queryParameters['after'], '3');
    expect(prefs.simPushLastSeq, 7);

    // A restart resumes after the last push seen: nothing is shown twice.
    final restarted = build();
    expect(await restarted.pollOnce(), isTrue);
    expect(adapter.requests.last.uri.queryParameters['after'], '7');
    expect(notifications.shown, hasLength(2));
  });

  test(
    'maps items to PushPayload, shown with [SIM] on their channel',
    () async {
      final sim = build();
      final received = <PushPayload>[];
      sim.onForeground.listen(received.add);
      inbox
        ..add(_item(1))
        ..add(_item(2, data: {'type': 'report_status', 'code': 'EH-1'}));
      await sim.pollOnce();
      await Future<void>.delayed(Duration.zero);

      expect(received, hasLength(2));
      expect(received[0].kind, PushKind.alert);
      expect(received[0].id, 'a-1');
      expect(received[0].title, 'Flood warning');
      expect(received[0].body, 'Move to higher ground');
      expect(received[0].route, '/alerts/a-1');
      expect(received[1].kind, PushKind.reportStatus);
      expect(received[1].data, {'type': 'report_status', 'code': 'EH-1'});

      expect(notifications.shown.map((s) => s.channelId), [
        'ehimaya_alerts',
        'ehimaya_alerts',
      ]);
      expect(notifications.shown.first.id, 1);
      expect(notifications.shown.first.payload.title, '[SIM] Flood warning');
      expect(pushChannelFor(received[1], 'ehimaya_default'), 'ehimaya_default');
      expect(pushChannelFor(received[1], 'bogus'), 'ehimaya_default');
    },
  );

  test('ignores malformed items but moves past them', () async {
    final sim = build();
    final received = <PushPayload>[];
    sim.onForeground.listen(received.add);
    adapter.handler = (_) => const FakeResponse(
      200,
      json: {
        'items': [
          'not an object',
          {
            'seq': 'x',
            'data': {'type': 'info'},
          },
          {'seq': 2, 'data': null, 'title': 't'},
          {
            'seq': 3,
            'data': {'type': 'unknown_kind'},
            'title': 't',
          },
          {
            'seq': 4,
            'data': ['type', 'info'],
            'title': 't',
          },
          {
            'seq': 5,
            'data': {'type': 'info'},
            'title': 42,
          },
        ],
        'last_seq': 5,
      },
    );
    expect(await sim.pollOnce(), isTrue);
    await Future<void>.delayed(Duration.zero);
    expect(received, hasLength(1));
    expect(received.single.kind, PushKind.info);
    expect(received.single.title, isNull);
    expect(notifications.shown, isEmpty); // nothing to display without title
    expect(prefs.simPushLastSeq, 5);

    adapter.handler = (_) => const FakeResponse(200, json: ['unexpected']);
    expect(await sim.pollOnce(), isFalse);
    expect(prefs.simPushLastSeq, 5);
  });

  test('network errors are silent and do not advance the sequence', () async {
    final sim = build();
    await prefs.setSimPushLastSeq(4);
    adapter.handler = (_) => const FakeResponse.network();
    expect(await sim.pollOnce(), isFalse);
    adapter.handler = (_) => const FakeResponse(503);
    expect(await sim.pollOnce(), isFalse);
    expect(prefs.simPushLastSeq, 4);
  });

  test('simulator restart (last_seq below after) starts over', () async {
    final sim = build();
    await prefs.setSimPushLastSeq(40);
    adapter.handler = (_) =>
        const FakeResponse(200, json: {'items': [], 'last_seq': 2});
    expect(await sim.pollOnce(), isTrue);
    expect(prefs.simPushLastSeq, 0);
  });

  test('polls only while in the foreground', () async {
    final sim = build(interval: const Duration(milliseconds: 10));
    expect(await sim.start(_names), isTrue);
    expect(sim.isPolling, isTrue);
    await Future<void>.delayed(const Duration(milliseconds: 60));
    expect(adapter.requests, isNotEmpty);

    sim.didChangeAppLifecycleState(AppLifecycleState.paused);
    expect(sim.isPolling, isFalse);
    await Future<void>.delayed(const Duration(milliseconds: 20));
    final count = adapter.requests.length;
    await Future<void>.delayed(const Duration(milliseconds: 60));
    expect(adapter.requests, hasLength(count));

    sim.didChangeAppLifecycleState(AppLifecycleState.resumed);
    expect(sim.isPolling, isTrue);
    await Future<void>.delayed(const Duration(milliseconds: 60));
    expect(adapter.requests.length, greaterThan(count));
  });

  test(
    'taps emit onOpened; the launch notification is returned once',
    () async {
      notifications.launch = PushPayload.parse({'type': 'callout'});
      final sim = build();
      final opened = <PushPayload>[];
      sim.onOpened.listen(opened.add);
      await sim.start(_names);
      sim.didChangeAppLifecycleState(AppLifecycleState.paused);

      expect((await sim.launchPayload())?.kind, PushKind.callout);
      expect(await sim.launchPayload(), isNull);
      notifications.onTap!(PushPayload.parse({'type': 'info'})!);
      await Future<void>.delayed(Duration.zero);
      expect(opened.single.kind, PushKind.info);
      expect(await sim.onTokenRefresh.isEmpty, isTrue);
    },
  );

  test('works without local notifications', () async {
    notifications.failInit = true;
    final sim = build();
    expect(await sim.start(_names), isTrue);
    sim.didChangeAppLifecycleState(AppLifecycleState.paused);
  });

  test('simulation is flagged only for an available simulated push', () {
    final sim = build();
    final container = ProviderContainer(
      overrides: [pushMessagingProvider.overrideWithValue(sim)],
    );
    addTearDown(container.dispose);
    expect(container.read(pushSimulationActiveProvider), isFalse);
    container.read(pushAvailableProvider.notifier).set(true);
    expect(container.read(pushSimulationActiveProvider), isTrue);

    final real = ProviderContainer(
      overrides: [
        pushMessagingProvider.overrideWithValue(const NoPushMessaging()),
      ],
    );
    addTearDown(real.dispose);
    real.read(pushAvailableProvider.notifier).set(true);
    expect(real.read(pushSimulationActiveProvider), isFalse);
  });

  group('simulation banner', () {
    Future<void> pump(WidgetTester tester, String lang, bool active) =>
        tester.pumpWidget(
          ProviderScope(
            overrides: [pushSimulationActiveProvider.overrideWithValue(active)],
            child: MaterialApp(
              locale: Locale(lang),
              localizationsDelegates: AppLocalizations.localizationsDelegates,
              supportedLocales: AppLocalizations.supportedLocales,
              home: const Scaffold(body: PushSimulationBanner()),
            ),
          ),
        );

    const labels = {
      'ar': 'وضع المحاكاة',
      'fr': 'Mode simulation',
      'en': 'Simulation mode',
    };
    for (final e in labels.entries) {
      testWidgets('shown in ${e.key} when simulated', (tester) async {
        await pump(tester, e.key, true);
        expect(find.byKey(const Key('push-simulation-banner')), findsOneWidget);
        expect(find.text(e.value), findsOneWidget);
        if (e.key == 'ar') {
          expect(
            Directionality.of(tester.element(find.text(e.value))),
            TextDirection.rtl,
          );
        }
      });
    }

    testWidgets('hidden with real push', (tester) async {
      await pump(tester, 'en', false);
      expect(find.byKey(const Key('push-simulation-banner')), findsNothing);
    });
  });

  test('the simulator client never sends identity headers', () {
    final dio = buildSimulatorDio('http://x:1');
    expect(dio.interceptors.whereType<IdentityInterceptor>(), isEmpty);
    expect(dio.options.baseUrl, 'http://x:1');
  });
}
