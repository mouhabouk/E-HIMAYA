import 'package:ehimaya/core/push/push_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/app_harness.dart';
import '../helpers/fake_http.dart';
import '../helpers/phase5_fixtures.dart';

/// Brings an entry of the current list into view (clear of the bottom navigation bar).
Future<void> scrollTo(WidgetTester tester, String key) async {
  final finder = find.byKey(Key(key));
  await tester.scrollUntilVisible(
    finder,
    200,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
}

void main() {
  final noPush = pushMessagingProvider.overrideWithValue(FakePushMessaging());

  testWidgets('a red alert is shown on home and opens its detail', (
    tester,
  ) async {
    await pumpApp(
      tester,
      prefs: onboardedPrefs(locale: 'fr'),
      overrides: [noPush],
      api: (r) {
        if (r.path == '/api/v1/alerts/active') {
          return FakeResponse(
            200,
            json: [
              alertJson(),
              alertJson(id: 'a2', severity: 'low'),
            ],
          );
        }
        return defaultApiResponse(r);
      },
    );
    final banner = find.byKey(const Key('high-alerts-banner'));
    expect(banner, findsOneWidget);
    // Only the high-severity alert is in the banner.
    expect(
      find.descendant(of: banner, matching: find.byType(ListTile)),
      findsOneWidget,
    );
    await tester.tap(find.text('Alerte pluies abondantes'));
    await tester.pumpAndSettle();
    expect(find.text('Évitez les oueds'), findsOneWidget);
    expect(find.text('Alerte rouge · Fortes pluies'), findsOneWidget);
    await unmountApp(tester);
  });

  testWidgets('notifications: alerts in force then the inbox (RTL)', (
    tester,
  ) async {
    await pumpApp(
      tester,
      prefs: onboardedPrefs(),
      overrides: [noPush],
      api: (r) => switch (r.path) {
        '/api/v1/alerts/active' => FakeResponse(200, json: [alertJson()]),
        '/api/v1/notifications' => FakeResponse(
          200,
          json: {
            'items': [inboxItemJson('i1')],
            'next_cursor': null,
          },
        ),
        _ => defaultApiResponse(r),
      },
    );
    await tester.tap(find.byKey(const Key('home-notifications')));
    await tester.pumpAndSettle();
    expect(find.text('التنبيهات السارية'), findsOneWidget);
    expect(find.text('تنبيه أمطار غزيرة'), findsOneWidget);
    expect(find.byKey(const Key('inbox-i1')), findsOneWidget);
    expect(
      Directionality.of(tester.element(find.text('الرسائل'))),
      TextDirection.rtl,
    );
    await tester.tap(find.text('يوم تحسيسي'));
    await tester.pumpAndSettle();
    expect(find.text('يوم مفتوح'), findsOneWidget);
    await unmountApp(tester);
  });

  testWidgets('safety tips are readable offline from the bundled copy', (
    tester,
  ) async {
    await pumpApp(
      tester,
      prefs: onboardedPrefs(locale: 'en'),
      overrides: [noPush],
      api: (_) => const FakeResponse.network(),
    );
    await scrollTo(tester, 'home-tips');
    await tester.tap(find.byKey(const Key('home-tips')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('tip-fire')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('tip-do')), findsOneWidget);
    expect(find.byKey(const Key('tip-dont')), findsOneWidget);
    expect(find.textContaining('198'), findsWidgets);
    await unmountApp(tester);
  });

  testWidgets(
    'approved volunteer accepts a call-out with an ETA, then arrives',
    (tester) async {
      var callout = calloutJson();
      await pumpApp(
        tester,
        prefs: registeredPrefs(locale: 'fr'),
        session: testSession,
        overrides: [noPush],
        api: (r) {
          switch ((r.method, r.path)) {
            case ('GET', '/api/v1/me/volunteer'):
              return FakeResponse(200, json: volunteerJson());
            case ('GET', '/api/v1/me/callouts'):
              return FakeResponse(200, json: [callout]);
            case ('POST', final p) when p.endsWith('/respond'):
              final body = r.json! as Map<String, Object?>;
              callout = {
                ...callout,
                'my_status': 'accepted',
                'eta_minutes': body['eta_minutes'],
              };
              return FakeResponse(200, json: callout);
            case ('POST', final p) when p.endsWith('/arrived'):
              callout = {...callout, 'my_status': 'arrived'};
              return FakeResponse(200, json: callout);
          }
          return defaultApiResponse(r);
        },
      );
      await scrollTo(tester, 'home-volunteer');
      await tester.tap(find.byKey(const Key('home-volunteer')));
      await tester.pumpAndSettle();
      expect(find.text('Acceptée'), findsOneWidget);
      expect(find.byKey(const Key('volunteer-ready')), findsOneWidget);

      await tester.ensureVisible(find.byKey(const Key('volunteer-callouts')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('volunteer-callouts')));
      await tester.pumpAndSettle();
      final id = callout['id']! as String;
      expect(find.text('À 2,4 km'), findsOneWidget);
      await tester.tap(find.byKey(Key('callout-accept-$id')));
      await tester.pumpAndSettle();
      await tester.enterText(find.byKey(const Key('callout-eta')), '0');
      await tester.pump();
      expect(
        tester
            .widget<FilledButton>(find.byKey(const Key('callout-eta-ok')))
            .onPressed,
        isNull,
      );
      await tester.enterText(find.byKey(const Key('callout-eta')), '12');
      await tester.pump();
      await tester.tap(find.byKey(const Key('callout-eta-ok')));
      await tester.pumpAndSettle();
      expect(find.text('En route'), findsOneWidget);
      expect(find.text('Arrivée dans 12 min'), findsOneWidget);

      await tester.tap(find.byKey(Key('callout-arrived-$id')));
      await tester.pumpAndSettle();
      expect(find.text('Sur place'), findsOneWidget);
      expect(find.byKey(Key('callout-arrived-$id')), findsNothing);
      await unmountApp(tester);
    },
  );

  testWidgets('volunteer application: skills required, profile_incomplete', (
    tester,
  ) async {
    Object? sent;
    await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'en'),
      session: testSession,
      overrides: [noPush],
      api: (r) {
        if (r.path == '/api/v1/me/volunteer' && r.method == 'GET') {
          return const FakeResponse(404, json: {'detail': 'not_volunteer'});
        }
        if (r.path == '/api/v1/me/volunteer' && r.method == 'PUT') {
          sent = r.json;
          return const FakeResponse(
            409,
            json: {'detail': 'profile_incomplete'},
          );
        }
        return defaultApiResponse(r);
      },
    );
    await scrollTo(tester, 'home-volunteer');
    await tester.tap(find.byKey(const Key('home-volunteer')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('volunteer-apply')));
    await tester.pumpAndSettle();

    await scrollTo(tester, 'volunteer-submit');
    await tester.tap(find.byKey(const Key('volunteer-submit')));
    await tester.pumpAndSettle();
    expect(find.text('Choose at least one skill.'), findsOneWidget);
    expect(sent, isNull);

    await scrollTo(tester, 'skill-first_aid');
    await tester.tap(find.byKey(const Key('skill-first_aid')));
    await tester.pump();
    await scrollTo(tester, 'volunteer-submit');
    await tester.tap(find.byKey(const Key('volunteer-submit')));
    await tester.pumpAndSettle();
    expect((sent! as Map)['skills'], ['first_aid']);
    expect(
      find.text('Complete your profile (phone and gouvernorate) first.'),
      findsOneWidget,
    );
    expect(find.widgetWithText(SnackBarAction, 'My profile'), findsOneWidget);
    await unmountApp(tester);
  });

  testWidgets('anonymous users are told volunteering needs an account', (
    tester,
  ) async {
    await pumpApp(
      tester,
      prefs: onboardedPrefs(locale: 'en'),
      overrides: [noPush],
    );
    expect(find.byKey(const Key('home-volunteer')), findsNothing);
    await unmountApp(tester);
  });
}
