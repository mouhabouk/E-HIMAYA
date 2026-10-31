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
Map<String, Object?> _prealert({String state = 'pending', String? reason}) => {
  'id': 'p-1',
  'org_id': 'org-1',
  'org_name': 'Entrepôt Sfax',
  'stream_id': 's-1',
  'source': 'camera',
  'label': 'smoke',
  'confidence': 0.82,
  'simulated': true,
  'state': state,
  'raised_at': DateTime.now().toUtc().toIso8601String(),
  'deadline_at': DateTime.now()
      .toUtc()
      .add(const Duration(seconds: 90))
      .toIso8601String(),
  'seconds_left': 90,
  'reason': reason,
  'report_id': state == 'confirmed' ? 'r-1' : null,
  'has_frame': false,
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
    await tester.tap(find.byKey(const Key('prealert-false')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('prealert-reason-cooking')));
    await tester.pumpAndSettle();
    final sent = h.adapter.requests.lastWhere(
      (r) => r.path.endsWith('/decision'),
    );
    expect(sent.json, {'action': 'cancel', 'reason': 'Cooking or barbecue'});
    expect(find.text('Cancelled: false alarm'), findsOneWidget);
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
}
