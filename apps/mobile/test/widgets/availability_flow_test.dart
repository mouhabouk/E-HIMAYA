// covers: phase N (docs/phase-n/design-n.md §8): a volunteer keeps an availability calendar in the app.
import 'package:ehimaya/core/push/push_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/app_harness.dart';
import '../helpers/fake_http.dart';
import '../helpers/phase5_fixtures.dart';
import 'phase5_flow_test.dart' show scrollTo;

void main() {
  final noPush = pushMessagingProvider.overrideWithValue(FakePushMessaging());

  testWidgets('a volunteer adds an away period on weekends and saves it', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1080, 3200);
    tester.view.devicePixelRatio = 2;
    addTearDown(tester.view.reset);
    Object? sent;
    await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'fr'),
      session: testSession,
      overrides: [noPush],
      api: (r) {
        switch ((r.method, r.path)) {
          case ('GET', '/api/v1/me/volunteer'):
            return FakeResponse(200, json: volunteerJson());
          case ('GET', '/api/v1/me/availability'):
            expect(r.uri.queryParameters['role'], 'volunteer');
            return const FakeResponse(
              200,
              json: {'role': 'volunteer', 'slots': [], 'planned_now': null},
            );
          case ('PUT', '/api/v1/me/availability'):
            sent = r.json;
            final slots = (r.json! as Map<String, Object?>)['slots']! as List;
            return FakeResponse(
              200,
              json: {
                'role': 'volunteer',
                'slots': [
                  for (final s in slots)
                    {...s as Map<String, Object?>, 'id': 'a1'},
                ],
                'planned_now': 'unavailable',
              },
            );
        }
        return defaultApiResponse(r);
      },
    );
    await scrollTo(tester, 'home-volunteer');
    await tester.tap(find.byKey(const Key('home-volunteer')));
    await tester.pumpAndSettle();
    await scrollTo(tester, 'volunteer-availability');
    await tester.tap(find.byKey(const Key('volunteer-availability')));
    await tester.pumpAndSettle();
    expect(find.text('Rien de prévu maintenant'), findsOneWidget);

    await tester.tap(find.byKey(const Key('availability-add')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Indisponible').last);
    await tester.tap(find.byKey(const Key('availability-day-6')));
    await tester.tap(find.byKey(const Key('availability-day-7')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('availability-ok')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('availability-slot-0')), findsOneWidget);

    await tester.tap(find.byKey(const Key('availability-save')));
    await tester.pumpAndSettle();
    final slot =
        ((sent! as Map<String, Object?>)['slots']! as List).single
            as Map<String, Object?>;
    expect(slot['kind'], 'unavailable');
    expect(slot['weekdays'], [6, 7]);
    expect(slot['from_time'], '08:00');
    expect(slot['to_time'], '20:00');
    expect(
      find.text('Indisponible maintenant selon votre calendrier'),
      findsOneWidget,
    );
    expect(find.text('Calendrier enregistré'), findsOneWidget);
    await unmountApp(tester);
  });
}
