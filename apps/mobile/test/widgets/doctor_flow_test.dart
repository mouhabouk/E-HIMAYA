// covers: phase C1-a (docs/phase-c/design-medical-axis.md §2): doctors register from the app.
import 'package:ehimaya/core/push/push_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/app_harness.dart';
import '../helpers/fake_http.dart';
import '../helpers/phase5_fixtures.dart';

Future<void> scrollTo(WidgetTester tester, String key) async {
  final finder = find.byKey(Key(key));
  if (finder.evaluate().isEmpty) {
    await tester.scrollUntilVisible(
      finder,
      200,
      scrollable: find.byType(Scrollable).first,
    );
  }
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
}

const gouvernorats = [
  {'code': 61, 'name': 'Sfax', 'name_ar': 'صفاقس', 'name_fr': 'Sfax'},
  {'code': 81, 'name': 'Gabès', 'name_ar': 'قابس', 'name_fr': 'Gabès'},
];

Map<String, Object?> doctorJson({
  String status = 'pending',
  String kind = 'civil_protection',
  bool available = false,
}) => {
  'kind': kind,
  'status': status,
  'specialties': ['emergency_medicine'],
  'licence_no': 'TN-12345',
  'workplace': 'Hôpital Habib Bourguiba',
  'gouvernorat_code': 61,
  'cp_unit': kind == 'civil_protection' ? 'Direction régionale' : null,
  'cp_staff_no': kind == 'civil_protection' ? 'PC/4521' : null,
  'review_reason': null,
  'submitted_at': '2026-10-24T08:00:00Z',
  'reviewed_at': null,
  'available': available,
  'available_until': available ? '2100-01-01T00:00:00Z' : null,
  'version': 1,
};

void main() {
  final noPush = pushMessagingProvider.overrideWithValue(FakePushMessaging());

  testWidgets('a Civil Protection doctor registers from the volunteer space', (
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
      api: (r) => switch ((r.method, r.path)) {
        ('GET', '/api/v1/me/volunteer') => const FakeResponse(
          404,
          json: {'detail': 'not_volunteer'},
        ),
        ('GET', '/api/v1/me/doctor') when sent == null => const FakeResponse(
          404,
          json: {'detail': 'not_doctor'},
        ),
        ('PUT', '/api/v1/me/doctor') => () {
          sent = r.json;
          return FakeResponse(200, json: doctorJson());
        }(),
        ('GET', '/api/v1/geo/gouvernorats') => const FakeResponse(
          200,
          json: gouvernorats,
        ),
        _ => defaultApiResponse(r),
      },
    );
    await scrollTo(tester, 'home-volunteer');
    await tester.tap(find.byKey(const Key('home-volunteer')));
    await tester.pumpAndSettle();
    await scrollTo(tester, 'doctor-join');
    await tester.tap(find.byKey(const Key('doctor-join')));
    await tester.pumpAndSettle();
    expect(find.text('Médecin volontaire'), findsOneWidget);
    await tester.tap(find.byKey(const Key('doctor-choose-civil_protection')));
    await tester.pumpAndSettle();

    // Nothing is sent before every required field is valid.
    await scrollTo(tester, 'doctor-submit');
    await tester.tap(find.byKey(const Key('doctor-submit')));
    await tester.pumpAndSettle();
    expect(find.text('Choisissez de 1 à 4 spécialités.'), findsOneWidget);
    expect(find.text('Vous devez accepter les conditions.'), findsOneWidget);
    expect(sent, isNull);

    await scrollTo(tester, 'specialty-emergency_medicine');
    await tester.tap(find.byKey(const Key('specialty-emergency_medicine')));
    await tester.pump();
    await tester.enterText(find.byKey(const Key('doctor-licence')), 'TN 1');
    await tester.enterText(
      find.byKey(const Key('doctor-workplace')),
      'Hôpital Habib Bourguiba',
    );
    await scrollTo(tester, 'doctor-gouvernorat');
    await tester.tap(find.byKey(const Key('doctor-gouvernorat')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Sfax').last);
    await tester.pumpAndSettle();
    await scrollTo(tester, 'doctor-cp-unit');
    await tester.enterText(
      find.byKey(const Key('doctor-cp-unit')),
      'Direction régionale',
    );
    await tester.enterText(find.byKey(const Key('doctor-cp-staff')), 'PC/4521');
    await scrollTo(tester, 'doctor-terms');
    await tester.tap(find.byKey(const Key('doctor-terms')));
    await scrollTo(tester, 'doctor-submit');
    await tester.tap(find.byKey(const Key('doctor-submit')));
    await tester.pumpAndSettle();
    // A space in the registration number is refused on the phone.
    expect(sent, isNull);
    await scrollTo(tester, 'doctor-licence');
    await tester.enterText(find.byKey(const Key('doctor-licence')), 'TN-12345');
    await scrollTo(tester, 'doctor-submit');
    await tester.tap(find.byKey(const Key('doctor-submit')));
    await tester.pumpAndSettle();

    expect(sent, {
      'kind': 'civil_protection',
      'specialties': ['emergency_medicine'],
      'licence_no': 'TN-12345',
      'workplace': 'Hôpital Habib Bourguiba',
      'gouvernorat_code': 61,
      'cp_unit': 'Direction régionale',
      'cp_staff_no': 'PC/4521',
      'terms_version': '1',
    });
    expect(find.byKey(const Key('doctor-status')), findsOneWidget);
    expect(find.textContaining('en cours de vérification'), findsOneWidget);
    // Not approved yet: no availability and no directory.
    expect(find.byKey(const Key('doctor-available')), findsNothing);
    expect(find.byKey(const Key('doctor-directory')), findsNothing);
    await unmountApp(tester);
  });

  testWidgets('an approved doctor is available and searches the directory', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1080, 3200);
    tester.view.devicePixelRatio = 2;
    addTearDown(tester.view.reset);
    final availability = <Object?>[];
    final queries = <Map<String, String>>[];
    var available = false;
    await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'en'),
      session: testSession,
      overrides: [noPush],
      api: (r) => switch ((r.method, r.path)) {
        ('GET', '/api/v1/me/volunteer') => const FakeResponse(
          404,
          json: {'detail': 'not_volunteer'},
        ),
        ('GET', '/api/v1/me/doctor') => FakeResponse(
          200,
          json: doctorJson(status: 'approved', available: available),
        ),
        ('POST', '/api/v1/me/doctor/availability') => () {
          availability.add(r.json);
          available = (r.json! as Map)['available'] == true;
          return FakeResponse(
            200,
            json: doctorJson(status: 'approved', available: available),
          );
        }(),
        ('GET', '/api/v1/doctors/directory') => () {
          queries.add(r.uri.queryParameters);
          return FakeResponse(
            200,
            json: [
              if (r.uri.queryParameters['specialty'] != 'toxicology')
                {
                  'id': 'd1',
                  'full_name': 'Salma Trabelsi',
                  'kind': 'volunteer',
                  'specialties': ['cardiology'],
                  'workplace': 'Clinique Ennasr',
                  'gouvernorat_code': 81,
                  'available': true,
                },
            ],
          );
        }(),
        ('GET', '/api/v1/geo/gouvernorats') => const FakeResponse(
          200,
          json: gouvernorats,
        ),
        _ => defaultApiResponse(r),
      },
    );
    await scrollTo(tester, 'home-volunteer');
    await tester.tap(find.byKey(const Key('home-volunteer')));
    await tester.pumpAndSettle();
    await scrollTo(tester, 'doctor-join');
    await tester.tap(find.byKey(const Key('doctor-join')));
    await tester.pumpAndSettle();
    expect(find.text('Civil Protection doctor'), findsOneWidget);
    expect(
      find.textContaining('Hôpital Habib Bourguiba · Sfax'),
      findsOneWidget,
    );

    await tester.tap(find.byKey(const Key('doctor-available')));
    await tester.pumpAndSettle();
    expect(availability, [
      {'available': true, 'hours': 8},
    ]);
    expect(find.textContaining('Available until'), findsOneWidget);

    await tester.tap(find.byKey(const Key('doctor-directory')));
    await tester.pumpAndSettle();
    expect(find.text('Salma Trabelsi'), findsOneWidget);
    expect(find.textContaining('Cardiology'), findsOneWidget);
    expect(find.textContaining('Clinique Ennasr · Gabès'), findsOneWidget);
    expect(queries.last, isEmpty);

    await tester.tap(find.byKey(const Key('directory-specialty')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Toxicology').last);
    await tester.pumpAndSettle();
    expect(queries.last, {'specialty': 'toxicology'});
    expect(find.byKey(const Key('directory-empty')), findsOneWidget);
    await unmountApp(tester);
  });

  testWidgets('a withdrawn doctor can register again', (tester) async {
    await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'ar'),
      session: testSession,
      overrides: [noPush],
      api: (r) => switch ((r.method, r.path)) {
        ('GET', '/api/v1/me/doctor') => FakeResponse(
          200,
          json: {
            ...doctorJson(status: 'withdrawn', kind: 'volunteer'),
            'licence_no': null,
          },
        ),
        _ => defaultApiResponse(r),
      },
    );
    await tester.tap(find.byIcon(Icons.settings_outlined));
    await tester.pumpAndSettle();
    await scrollTo(tester, 'settings-doctor');
    await tester.tap(find.byKey(const Key('settings-doctor')));
    await tester.pumpAndSettle();
    expect(find.text('طبيب متطوع'), findsOneWidget);
    expect(find.byKey(const Key('doctor-reapply')), findsOneWidget);
    expect(find.byKey(const Key('doctor-withdraw')), findsNothing);
    await unmountApp(tester);
  });
}
