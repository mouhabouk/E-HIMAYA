// covers: phase C1-a (docs/phase-c/design-medical-axis.md §2): doctors register from the app.
import 'dart:convert';

import 'package:ehimaya/core/crypto/medical_crypto.dart';
import 'package:ehimaya/core/push/push_messaging.dart';
import 'package:ehimaya/core/storage/secure_store.dart';
import 'package:ehimaya/features/doctor/doctor_key.dart';
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
  String? committeeUntil,
  bool hasKey = false,
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
  'committee_until': committeeUntil,
  'has_key': hasKey,
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
          json: doctorJson(
            status: 'approved',
            available: available,
            committeeUntil: '2027-10-19T08:00:00Z',
          ),
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
    // Appointed to the medical committee by the system administrator.
    expect(find.byKey(const Key('doctor-committee')), findsOneWidget);
    expect(
      find.textContaining('Member of the medical committee until'),
      findsOneWidget,
    );
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

  // Phase C1-b (design §12): a cheap code derivation keeps the tests fast.
  final cheapCrypto = medicalCryptoProvider.overrideWithValue(
    MedicalCrypto(
      kdf: const KdfParams(memoryKib: 8192, iterations: 1),
      isolates: false,
    ),
  );

  testWidgets('a verified doctor creates their key with a code they choose', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1080, 3200);
    tester.view.devicePixelRatio = 2;
    addTearDown(tester.view.reset);
    final secure = MemorySecureStore();
    Map<String, Object?>? sent;
    await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'en'),
      session: testSession,
      secure: secure,
      overrides: [noPush, cheapCrypto],
      api: (r) => switch ((r.method, r.path)) {
        ('GET', '/api/v1/me/volunteer') => const FakeResponse(
          404,
          json: {'detail': 'not_volunteer'},
        ),
        ('GET', '/api/v1/me/doctor') => FakeResponse(
          200,
          json: doctorJson(status: 'approved', hasKey: sent != null),
        ),
        ('PUT', '/api/v1/me/doctor/key') => () {
          sent = (r.json! as Map).cast<String, Object?>();
          return FakeResponse(
            200,
            json: doctorJson(status: 'approved', hasKey: true),
          );
        }(),
        _ => defaultApiResponse(r),
      },
    );
    await scrollTo(tester, 'home-volunteer');
    await tester.tap(find.byKey(const Key('home-volunteer')));
    await tester.pumpAndSettle();
    await scrollTo(tester, 'doctor-join');
    await tester.tap(find.byKey(const Key('doctor-join')));
    await tester.pumpAndSettle();
    await scrollTo(tester, 'doctor-key-create');
    await tester.tap(find.byKey(const Key('doctor-key-create')));
    await tester.pumpAndSettle();

    // Too short, then two different codes: refused before anything is made.
    await tester.enterText(find.byKey(const Key('doctor-code')), '123');
    await tester.tap(find.byKey(const Key('doctor-code-ok')));
    await tester.pump();
    expect(find.text('The code has 6 to 12 digits.'), findsOneWidget);
    await tester.enterText(find.byKey(const Key('doctor-code')), '482916');
    await tester.enterText(
      find.byKey(const Key('doctor-code-again')),
      '482917',
    );
    await tester.tap(find.byKey(const Key('doctor-code-ok')));
    await tester.pump();
    expect(find.text('The two codes differ.'), findsOneWidget);
    await tester.enterText(
      find.byKey(const Key('doctor-code-again')),
      '482916',
    );
    await tester.tap(find.byKey(const Key('doctor-code-ok')));
    await tester.pumpAndSettle();

    // The server got the public key and the backup only; the private key stays on the phone.
    final publicKey = base64.decode(sent!['public_key']! as String);
    expect(publicKey, hasLength(32));
    final local = secure.values[doctorKeyStoreKey]!;
    expect(jsonEncode(sent), isNot(contains(local)));
    final restored = await tester.runAsync(
      () => MedicalCrypto(isolates: false)
          .restore((sent!['backup']! as Map).cast<String, Object?>(), '482916'),
    );
    expect(restored!.publicKey, publicKey);
    expect(find.byKey(const Key('doctor-files')), findsOneWidget);
    await unmountApp(tester);
  });

  testWidgets('a committee member opens a locked file with a reason', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1080, 3200);
    tester.view.devicePixelRatio = 2;
    addTearDown(tester.view.reset);
    // The private key 00 01 … 1f, for which test/core/medical_crypto_test.dart has a locked file.
    final secure = MemorySecureStore({
      doctorKeyStoreKey: base64.encode(List.generate(32, (i) => i)),
    });
    final reasons = <Object?>[];
    await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'en'),
      session: testSession,
      secure: secure,
      overrides: [noPush, cheapCrypto],
      api: (r) => switch ((r.method, r.path)) {
        ('GET', '/api/v1/me/volunteer') => const FakeResponse(
          404,
          json: {'detail': 'not_volunteer'},
        ),
        ('GET', '/api/v1/me/doctor') => FakeResponse(
          200,
          json: doctorJson(
            status: 'approved',
            hasKey: true,
            committeeUntil: '2027-10-19T08:00:00Z',
          ),
        ),
        ('GET', '/api/v1/medical/files') => const FakeResponse(
          200,
          json: [
            {
              'report_id': 'r-1',
              'tracking_code': 'EH-26-61-0004821',
              'category': 'medical',
              'gouvernorat_code': 61,
              'received_at': '2026-10-24T08:00:00Z',
              'report_status': 'received',
              'via': 'committee',
              'opened_at': null,
            },
          ],
        ),
        ('POST', '/api/v1/medical/files/r-1/open') => () {
          reasons.add((r.json! as Map)['reason']);
          return const FakeResponse(
            200,
            json: {
              'report_id': 'r-1',
              'via': 'committee',
              'nonce': 'YXEwdh0uwmwCycUO',
              'ciphertext': 'ZysKJHcjre7NuqlKJHQOJt918tE6eNcYl2VyiMkxvR8lVL8/C7tuPCBxwwmmO9pWduJi5J4sICjl5ePXHGL5sczmtTftppBc0A==',
              'eph_public': '/e4H227C6kwXS3cybUy4NFwPyfJpBghhzIvkSIXD1Bo=',
              'key_nonce': 'lEcmkiYvK/AGhpNl',
              'wrapped': 'FhEubSLgukgMHXgurNN2z7T0rownMe/YKPwTf50cdquwZR5AVj9RnSkpO9U1VfC0',
              'card': {'blood_group': 'AB-'},
            },
          );
        }(),
        _ => defaultApiResponse(r),
      },
    );
    await scrollTo(tester, 'home-volunteer');
    await tester.tap(find.byKey(const Key('home-volunteer')));
    await tester.pumpAndSettle();
    await scrollTo(tester, 'doctor-join');
    await tester.tap(find.byKey(const Key('doctor-join')));
    await tester.pumpAndSettle();
    await scrollTo(tester, 'doctor-files');
    await tester.tap(find.byKey(const Key('doctor-files')));
    await tester.pumpAndSettle();
    expect(find.textContaining('EH-26-61-0004821'), findsOneWidget);
    expect(find.textContaining('Medical committee'), findsOneWidget);

    await tester.tap(find.byKey(const Key('file-r-1')));
    await tester.pumpAndSettle();
    // No reason, no opening.
    await tester.tap(find.byKey(const Key('file-reason-ok')));
    await tester.pumpAndSettle();
    expect(reasons, isEmpty);
    await tester.enterText(
      find.byKey(const Key('file-reason')),
      'Quality review',
    );
    await tester.tap(find.byKey(const Key('file-reason-ok')));
    await tester.pumpAndSettle();
    expect(reasons, ['Quality review']);
    final text = tester.widget<Text>(find.byKey(const Key('file-text'))).data!;
    expect(text, contains('AB-'));
    expect(text, contains('insuline'));
    expect(text, contains('diabète'));
    await unmountApp(tester);
  });
}
