import 'package:ehimaya/core/push/push_messaging.dart';
import 'package:ehimaya/core/push/push_notifications.dart';
import 'package:ehimaya/core/push/push_payload.dart';
import 'package:ehimaya/core/routing/app_router.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/app_harness.dart';
import '../helpers/fake_http.dart';

Future<void> go(WidgetTester tester, String location) async {
  final context = tester.element(find.byType(Scaffold).first);
  ProviderScope.containerOf(context).read(routerProvider).go(location);
  await tester.pumpAndSettle();
}

Map<String, Object?> _body(SeenRequest r) => r.json! as Map<String, Object?>;

/// Review point 25 (phase D): the owner's pre-alert screen.
Map<String, Object?> _prealert({
  String state = 'pending',
  String? reason,
  String stage = 'officer',
}) => {
  'id': 'p-1',
  'org_id': 'org-1',
  'org_name': 'Entrepôt Sfax',
  'stream_id': 's-1',
  'source': 'camera',
  'label': 'smoke',
  'confidence': 0.82,
  'simulated': true,
  'state': state,
  'stage': stage,
  'raised_at': DateTime.now().toUtc().toIso8601String(),
  'deadline_at': DateTime.now()
      .toUtc()
      .add(const Duration(seconds: 60))
      .toIso8601String(),
  'seconds_left': 60,
  'reason': reason,
  'report_id': state == 'confirmed' ? 'r-1' : null,
  'has_frame': false,
};

FakeResponse Function(SeenRequest) _apiWith(Map<String, Object?> row) =>
    (r) => switch ((r.method, r.path)) {
      ('GET', '/api/v1/orgs/org-1/prealerts') => FakeResponse(200, json: [row]),
      _ => _api(r),
    };

FakeResponse _api(SeenRequest r) => switch ((r.method, r.path)) {
  ('GET', '/api/v1/orgs/org-1/prealerts') => FakeResponse(
    200,
    json: [_prealert()],
  ),
  ('POST', '/api/v1/orgs/org-1/prealerts/p-1/decision') => FakeResponse(
    200,
    json: _prealert(
      state: _body(r)['action'] == 'confirm' ? 'confirmed' : 'cancelled',
      reason: _body(r)['reason'] as String?,
    ),
  ),
  _ => defaultApiResponse(r),
};

void main() {
  test('the push opens the pre-alert of the institution', () {
    final p = PushPayload.parse({
      'type': 'prealert',
      'prealert_id': 'p-1',
      'org_id': 'org-1',
      'redacted': '1',
    })!;
    expect(p.kind, PushKind.prealert);
    expect(p.kind.urgent, isTrue);
    expect(p.route, Routes.prealert('org-1', 'p-1'));
  });

  testWidgets('countdown, then a false alarm with a ready reason', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1080, 2800);
    tester.view.devicePixelRatio = 2;
    addTearDown(tester.view.reset);
    final h = await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'en'),
      session: testSession,
      api: _api,
    );
    await go(tester, Routes.prealert('org-1', 'p-1'));
    expect(find.textContaining('Smoke · 82%'), findsOneWidget);
    expect(find.byKey(const Key('sim-banner')), findsOneWidget);
    expect(find.byKey(const Key('prealert-countdown')), findsOneWidget);
    expect(find.textContaining("Safety officer's turn"), findsOneWidget);
    // Three tiles: the picture, confirm (SOS), false alarm or unconfirmed.
    expect(find.byKey(const Key('prealert-media')), findsOneWidget);
    expect(find.text('Confirm the report (SOS)'), findsOneWidget);
    expect(find.text('False alarm or unconfirmed'), findsOneWidget);
    await tester.tap(find.byKey(const Key('prealert-false')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('prealert-reason-cooking')));
    await tester.pumpAndSettle();
    final sent = h.adapter.requests.lastWhere(
      (r) => r.path.endsWith('/decision'),
    );
    expect(sent.json, {'action': 'cancel', 'reason': 'Cooking or barbecue'});
    expect(find.text('Cancelled: false alarm or unconfirmed'), findsOneWidget);
    await unmountApp(tester);
  });

  testWidgets('confirm sends the report at once', (tester) async {
    tester.view.physicalSize = const Size(1080, 2800);
    tester.view.devicePixelRatio = 2;
    addTearDown(tester.view.reset);
    final h = await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'ar'),
      session: testSession,
      api: _api,
    );
    await go(tester, Routes.prealert('org-1', 'p-1'));
    await tester.tap(find.byKey(const Key('prealert-confirm')));
    await tester.pumpAndSettle();
    expect(
      h.adapter.requests.lastWhere((r) => r.path.endsWith('/decision')).json,
      {'action': 'confirm'},
    );
    expect(find.text('أُكّد وأُبلغت القاعة'), findsOneWidget);
    await unmountApp(tester);
  });

  testWidgets('the alarm rings while it waits and stops when silenced', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1080, 2800);
    tester.view.devicePixelRatio = 2;
    addTearDown(tester.view.reset);
    final alarm = FakePrealertAlarm();
    await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'ar'),
      session: testSession,
      api: _apiWith(_prealert(stage: 'owner')),
      alarm: alarm,
    );
    await go(tester, Routes.prealert('org-1', 'p-1'));
    expect(alarm.ringing, isTrue);
    expect(find.textContaining('دور صاحب المؤسسة'), findsOneWidget);
    await tester.tap(find.byKey(const Key('prealert-mute')));
    await tester.pumpAndSettle();
    expect(alarm.ringing, isFalse);
    expect(find.byKey(const Key('prealert-mute')), findsNothing);
    await unmountApp(tester);
  });

  testWidgets('a device the Civil Protection follows says the room was told', (
    tester,
  ) async {
    final alarm = FakePrealertAlarm();
    await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'ar'),
      session: testSession,
      api: _apiWith(_prealert(state: 'escalated', stage: 'room')),
      alarm: alarm,
    );
    await go(tester, Routes.prealert('org-1', 'p-1'));
    expect(alarm.starts, 0);
    expect(
      find.text('جهاز تتابعه الحماية المدنية: أُبلغت القاعة مباشرة'),
      findsOneWidget,
    );
    await unmountApp(tester);
  });

  test('the pre-alert rings on its own alarm channel', () {
    final p = PushPayload.parse({
      'type': 'prealert',
      'prealert_id': 'p-1',
      'org_id': 'org-1',
    })!;
    expect(pushChannelFor(p), prealertChannelId);
    expect(pushChannelFor(p, criticalChannelId, true), prealertChannelId);
  });
}
