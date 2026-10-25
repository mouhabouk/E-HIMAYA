// covers: backlog G3 (docs/backlog.md): the environment strip above every screen.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/app_harness.dart';
import '../helpers/fake_http.dart';

FakeHandler _version(String? environment) =>
    (r) => r.path == '/api/v1/app/version'
    ? FakeResponse(
        200,
        json: {
          'latest_version': '0.9.0',
          'latest_build': 1,
          'min_build': 1,
          'notes': {'ar': '', 'fr': '', 'en': ''},
          'channel': 'server',
          'download_url': null,
          'update_available': false,
          'mandatory': false,
          'sms_simulated': false,
          'environment': environment,
        },
      )
    : defaultApiResponse(r);

void main() {
  testWidgets('a pilot server shows the amber strip with its [SIM] word', (
    tester,
  ) async {
    await pumpApp(tester, prefs: onboardedPrefs(), api: _version('pilot'));
    await tester.pump(const Duration(seconds: 1));
    await tester.pump(const Duration(seconds: 1));
    final strip = find.byKey(const Key('environment-strip'));
    expect(strip, findsOneWidget);
    expect(
      find.descendant(of: strip, matching: find.textContaining('[SIM]')),
      findsOneWidget,
    );
    await unmountApp(tester);
  });

  testWidgets('production (no environment) shows no strip', (tester) async {
    await pumpApp(tester, prefs: onboardedPrefs(), api: _version(null));
    await tester.pump(const Duration(seconds: 1));
    await tester.pump(const Duration(seconds: 1));
    expect(find.byKey(const Key('environment-strip')), findsNothing);
    await unmountApp(tester);
  });

  testWidgets('the strip never calls the server before the charter', (
    tester,
  ) async {
    final h = await pumpApp(
      tester,
      prefs: languageAndIntroDone,
      api: _version('pilot'),
    );
    await tester.pumpAndSettle();
    expect(h.adapter.requests, isEmpty);
    expect(find.byKey(const Key('environment-strip')), findsNothing);
    await unmountApp(tester);
  });
}
