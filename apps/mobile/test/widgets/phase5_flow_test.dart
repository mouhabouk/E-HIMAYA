import 'package:ehimaya/core/push/push_messaging.dart';
import 'package:ehimaya/features/report/sms_fallback.dart';
import 'package:ehimaya/features/volunteer/callout_sms.dart';
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

  testWidgets('first readiness asks for the location consent', (tester) async {
    var volunteer = volunteerJson();
    final posted = <String>[];
    await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'fr'),
      session: testSession,
      overrides: [noPush],
      api: (r) {
        switch ((r.method, r.path)) {
          case ('GET', '/api/v1/me/volunteer'):
            return FakeResponse(200, json: volunteer);
          case ('GET', '/api/v1/me/callouts'):
            return const FakeResponse(200, json: <Object?>[]);
          case ('POST', '/api/v1/me/consents'):
            posted.add(r.path);
            volunteer = {...volunteer, 'location_consent': true};
            return const FakeResponse(204);
          case ('POST', '/api/v1/me/volunteer/readiness'):
            posted.add(r.path);
            volunteer = {
              ...volunteer,
              'ready': true,
              'ready_until': '2100-01-01T00:00:00Z',
            };
            return FakeResponse(200, json: volunteer);
        }
        return defaultApiResponse(r);
      },
    );
    await scrollTo(tester, 'home-volunteer');
    await tester.tap(find.byKey(const Key('home-volunteer')));
    await tester.pumpAndSettle();

    // Declining the notice leaves the volunteer not ready, and nothing is sent.
    await tester.tap(find.byKey(const Key('volunteer-ready')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('location-consent-dialog')), findsOneWidget);
    await tester.tap(find.text('Annuler'));
    await tester.pumpAndSettle();
    expect(posted, isEmpty);

    await tester.tap(find.byKey(const Key('volunteer-ready')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('location-consent-accept')));
    await tester.pumpAndSettle();
    expect(posted, ['/api/v1/me/consents', '/api/v1/me/volunteer/readiness']);
    final consent = tester.widget<SwitchListTile>(
      find.byKey(const Key('volunteer-location-consent')),
    );
    expect(consent.value, isTrue);
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

      await scrollTo(tester, 'volunteer-callouts');
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

  test('EH3: the signed answer matches the server (S2-5)', () {
    final body = eh3Body(
      key: '0123456789abcdef0123456789abcdef',
      volunteerId: '0f0f0f0f-0f0f-0f0f-0f0f-0f0f0f0f0f0f',
      calloutId: '1a1a1a1a-1a1a-1a1a-1a1a-1a1a1a1a1a1a',
      reply: 'accept',
      eta: 15,
      at: DateTime.fromMillisecondsSinceEpoch(1793440800 * 1000, isUtc: true),
    );
    expect(
      body,
      'EH3 ${'0f' * 16} ${'1a' * 16} accept 15 1793440800 5ecd7484666c7b9a',
    );
    expect(
      eh3Body(
        key: 'k',
        volunteerId: '0f' * 16,
        calloutId: '1a' * 16,
        reply: 'decline',
        eta: 9,
        at: DateTime.fromMillisecondsSinceEpoch(1793440800 * 1000),
      ).split(' ')[4],
      '0',
    );
  });

  testWidgets(
    'offline, the volunteer accepts a call-out by signed SMS (S2-5)',
    (tester) async {
      final callout = calloutJson();
      final sms = <Uri>[];
      var keys = 0;
      await pumpApp(
        tester,
        prefs: registeredPrefs(locale: 'fr'),
        session: testSession,
        overrides: [
          noPush,
          smsReportNumberProvider.overrideWithValue('+21671000000'),
          smsComposerProvider.overrideWithValue((uri) async {
            sms.add(uri);
            return true;
          }),
        ],
        api: (r) {
          switch ((r.method, r.path)) {
            case ('GET', '/api/v1/me/volunteer'):
              return FakeResponse(200, json: volunteerJson());
            case ('GET', '/api/v1/me/callouts'):
              return FakeResponse(200, json: [callout]);
            case ('POST', '/api/v1/me/volunteer/sms-key'):
              keys++;
              return FakeResponse(
                200,
                json: {
                  'key': '0123456789abcdef0123456789abcdef',
                  'volunteer_id': '0f0f0f0f-0f0f-0f0f-0f0f-0f0f0f0f0f0f',
                },
              );
            case ('POST', final p) when p.endsWith('/respond'):
              return const FakeResponse.network();
          }
          return defaultApiResponse(r);
        },
      );
      await scrollTo(tester, 'home-volunteer');
      await tester.tap(find.byKey(const Key('home-volunteer')));
      await tester.pumpAndSettle();
      await scrollTo(tester, 'volunteer-callouts');
      await tester.tap(find.byKey(const Key('volunteer-callouts')));
      await tester.pumpAndSettle();
      expect(keys, 1);
      final id = callout['id']! as String;
      await tester.tap(find.byKey(Key('callout-accept-$id')));
      await tester.pumpAndSettle();
      await tester.enterText(find.byKey(const Key('callout-eta')), '20');
      await tester.pump();
      await tester.tap(find.byKey(const Key('callout-eta-ok')));
      await tester.pumpAndSettle();
      expect(sms, hasLength(1));
      expect(sms.single.path, '+21671000000');
      final parts = sms.single.queryParameters['body']!.split(' ');
      expect(parts.take(4), [
        'EH3',
        '0f' * 16,
        id.replaceAll('-', ''),
        'accept',
      ]);
      expect(parts[4], '20');
      expect(parts.last, hasLength(16));
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
