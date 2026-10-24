// covers: phase C1-c (docs/phase-c/design-medical-axis.md §13): referrals, locked opinions, keys
// for a new committee member, and the reporter's "who saw my medical file".
import 'dart:convert';

import 'package:ehimaya/core/crypto/medical_crypto.dart';
import 'package:ehimaya/core/push/push_messaging.dart';
import 'package:ehimaya/core/routing/app_router.dart';
import 'package:ehimaya/core/storage/secure_store.dart';
import 'package:ehimaya/features/doctor/doctor_key.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../helpers/app_harness.dart';
import '../helpers/fake_http.dart';
import '../helpers/phase5_fixtures.dart';
import 'doctor_flow_test.dart' show doctorJson, gouvernorats;

// The file of test/core/medical_crypto_test.dart, locked for the private key 00 01 … 1f.
const _myPublic = 'j0DFrbaPJWJK5bIU6nZ6bslNgp09e14a0bpvPiE4KF8=';
const _opened = <String, Object?>{
  'report_id': 'r-1',
  'nonce': 'YXEwdh0uwmwCycUO',
  'ciphertext': 'ZysKJHcjre7NuqlKJHQOJt918tE6eNcYl2VyiMkxvR8lVL8/C7tuPCBxwwmmO9pWduJi5J4sICjl5ePXHGL5sczmtTftppBc0A==',
  'eph_public': '/e4H227C6kwXS3cybUy4NFwPyfJpBghhzIvkSIXD1Bo=',
  'key_nonce': 'lEcmkiYvK/AGhpNl',
  'wrapped': 'FhEubSLgukgMHXgurNN2z7T0rownMe/YKPwTf50cdquwZR5AVj9RnSkpO9U1VfC0',
  'card': {'blood_group': 'AB-'},
};
const _opinion = 'Échographie cardiaque sous 48 h.';

Map<String, Object?> _inbox(String via) => {
  'report_id': 'r-1',
  'tracking_code': 'EH-26-61-0004821',
  'category': 'medical',
  'gouvernorat_code': 61,
  'received_at': '2026-10-24T08:00:00Z',
  'report_status': 'received',
  'via': via,
  'opened_at': null,
};

/// A copy of a locked body for one doctor, as the server returns it.
Map<String, Object?> _copy(Map<String, Object?> locked, String doctorId) {
  final k = (locked['keys']! as List).cast<Map<String, Object?>>().firstWhere(
    (k) => k['doctor_id'] == doctorId,
  );
  return {
    'nonce': locked['nonce'],
    'ciphertext': locked['ciphertext'],
    'eph_public': k['eph_public'],
    'key_nonce': k['nonce'],
    'wrapped': k['wrapped'],
  };
}

Future<void> go(WidgetTester tester, String location) async {
  final context = tester.element(find.byType(Scaffold).first);
  ProviderScope.containerOf(context).read(routerProvider).go(location);
  await tester.pumpAndSettle();
}

void main() {
  final noPush = pushMessagingProvider.overrideWithValue(FakePushMessaging());
  final crypto = MedicalCrypto(
    kdf: const KdfParams(memoryKib: 8192, iterations: 1),
    isolates: false,
  );
  final cheapCrypto = medicalCryptoProvider.overrideWithValue(crypto);
  MemorySecureStore mySecure() => MemorySecureStore({
    doctorKeyStoreKey: base64.encode(List.generate(32, (i) => i)),
  });

  void tall(WidgetTester tester) {
    tester.view.physicalSize = const Size(1080, 3200);
    tester.view.devicePixelRatio = 2;
    addTearDown(tester.view.reset);
  }

  testWidgets(
    'a Civil Protection doctor reads an opinion and refers the file on the phone',
    (tester) async {
      tall(tester);
      final heart = await crypto.newKey();
      final opinion = await crypto.lock(
        {'text': _opinion},
        {'me': base64.decode(_myPublic)},
      );
      Map<String, Object?>? referral;
      await pumpApp(
        tester,
        prefs: registeredPrefs(locale: 'en'),
        session: testSession,
        secure: mySecure(),
        overrides: [noPush, cheapCrypto],
        api: (r) => switch ((r.method, r.path)) {
          ('GET', '/api/v1/me/doctor') => FakeResponse(
            200,
            json: doctorJson(status: 'approved', hasKey: true),
          ),
          ('GET', '/api/v1/geo/gouvernorats') => const FakeResponse(
            200,
            json: gouvernorats,
          ),
          ('GET', '/api/v1/medical/files') => FakeResponse(
            200,
            json: [_inbox('gouvernorat')],
          ),
          ('POST', '/api/v1/medical/files/r-1/open') => const FakeResponse(
            200,
            json: {..._opened, 'via': 'gouvernorat'},
          ),
          ('GET', '/api/v1/medical/files/r-1/opinions') => FakeResponse(
            200,
            json: [
              {
                'id': 'o-1',
                'report_id': 'r-1',
                'specialty': 'cardiology',
                'mine': false,
                'created_at': '2026-10-24T09:00:00Z',
                ..._copy(opinion, 'me'),
              },
            ],
          ),
          ('GET', '/api/v1/medical/files/r-1/referrals') => const FakeResponse(
            200,
            json: [],
          ),
          ('GET', '/api/v1/doctors/directory') => FakeResponse(
            200,
            json: [
              {
                'id': 's-1',
                'full_name': 'Dr Salma',
                'kind': 'volunteer',
                'specialties': ['cardiology'],
                'workplace': 'CHU Hédi Chaker',
                'gouvernorat_code': 61,
                'available': true,
                'public_key': base64.encode(heart.publicKey),
              },
              {
                'id': 's-2',
                'full_name': 'Dr Karim',
                'kind': 'volunteer',
                'specialties': ['cardiology'],
                'workplace': 'Clinique Ennasr',
                'gouvernorat_code': 81,
                'available': false,
                'public_key': null,
              },
            ],
          ),
          ('POST', '/api/v1/medical/files/r-1/referrals') => () {
            referral = (r.json! as Map).cast<String, Object?>();
            return const FakeResponse(204);
          }(),
          _ => defaultApiResponse(r),
        },
      );
      await go(tester, Routes.doctorFiles);
      await tester.tap(find.byKey(const Key('file-r-1')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('pending-members')), findsNothing);
      // The opinion is opened on this phone.
      expect(find.text(_opinion), findsOneWidget);
      expect(find.textContaining('Cardiology'), findsOneWidget);
      expect(find.byKey(const Key('write-opinion')), findsNothing);

      await tester.tap(find.byKey(const Key('refer')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('referral-specialty')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Cardiology').last);
      await tester.pumpAndSettle();
      // A doctor without a key cannot be chosen.
      final keyless = tester.widget<CheckboxListTile>(
        find.byKey(const Key('referral-s-2')),
      );
      expect(keyless.onChanged, isNull);
      await tester.tap(find.byKey(const Key('referral-s-1')));
      await tester.enterText(
        find.byKey(const Key('referral-reason')),
        'Cardiology opinion',
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('referral-send')));
      await tester.pumpAndSettle();

      expect(referral!['reason'], 'Cardiology opinion');
      final keys = (referral!['keys']! as List).cast<Map<String, Object?>>();
      expect(keys.map((k) => k['doctor_id']), ['s-1']);
      // The specialist opens the file with the key locked for them; the server got no clear text.
      final theirs = {
        ..._opened,
        ..._copy({..._opened, 'keys': keys}, 's-1'),
      };
      expect((await crypto.open(theirs, heart))['medications'], 'insuline');
      expect(jsonEncode(referral), isNot(contains('insuline')));
      expect(find.byKey(const Key('refer')), findsOneWidget);
      await unmountApp(tester);
    },
  );

  testWidgets('a specialist writes an opinion locked for the readers', (
    tester,
  ) async {
    tall(tester);
    final cp = await crypto.newKey();
    Map<String, Object?>? sent;
    await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'en'),
      session: testSession,
      secure: mySecure(),
      overrides: [noPush, cheapCrypto],
      api: (r) => switch ((r.method, r.path)) {
        ('GET', '/api/v1/me/doctor') => FakeResponse(
          200,
          json: doctorJson(status: 'approved', hasKey: true, kind: 'volunteer'),
        ),
        ('GET', '/api/v1/medical/files') => FakeResponse(
          200,
          json: [_inbox('referral')],
        ),
        ('POST', '/api/v1/medical/files/r-1/open') => const FakeResponse(
          200,
          json: {..._opened, 'via': 'referral'},
        ),
        ('GET', '/api/v1/medical/files/r-1/opinions') => const FakeResponse(
          200,
          json: [],
        ),
        ('GET', '/api/v1/medical/files/r-1/opinion-recipients') => FakeResponse(
          200,
          json: [
            {'doctor_id': 'me', 'public_key': _myPublic, 'role': 'author'},
            {
              'doctor_id': 'cp',
              'public_key': base64.encode(cp.publicKey),
              'role': 'referrer',
            },
          ],
        ),
        ('POST', '/api/v1/medical/files/r-1/opinions') => () {
          sent = (r.json! as Map).cast<String, Object?>();
          return const FakeResponse(201, json: {'id': 'o-1'});
        }(),
        _ => defaultApiResponse(r),
      },
    );
    await go(tester, Routes.doctorFiles);
    await tester.tap(find.byKey(const Key('file-r-1')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('refer')), findsNothing);
    await tester.tap(find.byKey(const Key('write-opinion')));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('opinion-text')), _opinion);
    await tester.tap(find.byKey(const Key('opinion-send')));
    await tester.pumpAndSettle();

    expect(jsonEncode(sent), isNot(contains('chographie')));
    expect(await crypto.open(_copy(sent!, 'cp'), cp), {'text': _opinion});
    expect(
      (sent!['keys']! as List).map((k) => (k as Map)['doctor_id']).toSet(),
      {'me', 'cp'},
    );
    await unmountApp(tester);
  });

  testWidgets('a committee member locks the files for a new member', (
    tester,
  ) async {
    tall(tester);
    final newcomer = await crypto.newKey();
    final opinion = await crypto.lock(
      {'text': _opinion},
      {'me': base64.decode(_myPublic)},
    );
    final shared = <String, Map<String, Object?>>{};
    final reasons = <Object?>[];
    await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'en'),
      session: testSession,
      secure: mySecure(),
      overrides: [noPush, cheapCrypto],
      api: (r) => switch ((r.method, r.path)) {
        ('GET', '/api/v1/me/doctor') => FakeResponse(
          200,
          json: doctorJson(
            status: 'approved',
            hasKey: true,
            committeeUntil: '2100-01-01T00:00:00Z',
          ),
        ),
        ('GET', '/api/v1/medical/files') => FakeResponse(
          200,
          json: [_inbox('committee')],
        ),
        ('GET', '/api/v1/medical/committee/pending') => FakeResponse(
          200,
          json: shared.length == 2
              ? const <Object?>[]
              : [
                  {
                    'doctor_id': 'm-2',
                    'full_name': 'Dr Nour',
                    'public_key': base64.encode(newcomer.publicKey),
                    'files': ['r-1'],
                    'opinions': [
                      {'id': 'o-1', 'report_id': 'r-1'},
                    ],
                  },
                ],
        ),
        ('POST', '/api/v1/medical/files/r-1/open') => () {
          reasons.add((r.json! as Map)['reason']);
          return const FakeResponse(
            200,
            json: {..._opened, 'via': 'committee'},
          );
        }(),
        ('GET', '/api/v1/medical/files/r-1/opinions') => FakeResponse(
          200,
          json: [
            {
              'id': 'o-1',
              'report_id': 'r-1',
              'specialty': 'cardiology',
              'mine': false,
              'created_at': '2026-10-24T09:00:00Z',
              ..._copy(opinion, 'me'),
            },
          ],
        ),
        ('POST', '/api/v1/medical/files/r-1/keys') ||
        ('POST', '/api/v1/medical/opinions/o-1/keys') => () {
          shared[r.path] = (r.json! as Map).cast<String, Object?>();
          return const FakeResponse(204);
        }(),
        _ => defaultApiResponse(r),
      },
    );
    await go(tester, Routes.doctorFiles);
    expect(find.textContaining('2 item(s) for Dr Nour'), findsOneWidget);
    await tester.tap(find.byKey(const Key('pending-share-m-2')));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('file-reason')), 'New member');
    await tester.tap(find.byKey(const Key('file-reason-ok')));
    await tester.pumpAndSettle();

    expect(reasons, ['New member']);
    final file = shared['/api/v1/medical/files/r-1/keys']!;
    expect(file['reason'], 'New member');
    final fileKeys = (file['keys']! as List).cast<Map<String, Object?>>();
    final theirFile = {
      ..._opened,
      ..._copy({..._opened, 'keys': fileKeys}, 'm-2'),
    };
    expect((await crypto.open(theirFile, newcomer))['conditions'], 'diabète');
    final op = shared['/api/v1/medical/opinions/o-1/keys']!;
    final theirOpinion = _copy({...opinion, 'keys': op['keys']}, 'm-2');
    expect(await crypto.open(theirOpinion, newcomer), {'text': _opinion});
    expect(find.byKey(const Key('pending-members')), findsNothing);
    await unmountApp(tester);
  });

  testWidgets('the reporter sees who saw their medical file, by role only', (
    tester,
  ) async {
    tall(tester);
    await pumpApp(
      tester,
      prefs: registeredPrefs(locale: 'en'),
      session: testSession,
      overrides: [noPush],
      api: (r) => switch ((r.method, r.path)) {
        ('GET', '/api/v1/reports/mine') => const FakeResponse(
          200,
          json: {
            'items': [
              {
                'id': 'r-1',
                'tracking_code': 'EH-26-61-0004821',
                'client_uuid': 'u1',
                'category': 'medical',
                'status': 'in_progress',
                'created_at': '2026-10-24T08:00:00Z',
                'media': <Object?>[],
              },
            ],
            'next_before': null,
          },
        ),
        ('GET', '/api/v1/geo/gouvernorats') => const FakeResponse(
          200,
          json: gouvernorats,
        ),
        ('GET', '/api/v1/me/medical/openings') => const FakeResponse(
          200,
          json: [
            {
              'report_id': 'r-1',
              'tracking_code': 'EH-26-61-0004821',
              'kind': 'open',
              'role': 'committee',
              'gouvernorat_code': null,
              'specialties': <Object?>[],
              'workplace': null,
              'at': '2026-10-24T11:00:00Z',
            },
            {
              'report_id': 'r-1',
              'tracking_code': 'EH-26-61-0004821',
              'kind': 'referral',
              'role': 'specialist',
              'gouvernorat_code': null,
              'specialties': ['cardiology'],
              'workplace': 'CHU Hédi Chaker',
              'at': '2026-10-24T10:00:00Z',
            },
            {
              'report_id': 'r-1',
              'tracking_code': 'EH-26-61-0004821',
              'kind': 'open',
              'role': 'civil_protection',
              'gouvernorat_code': 61,
              'specialties': <Object?>[],
              'workplace': null,
              'at': '2026-10-24T09:00:00Z',
            },
          ],
        ),
        _ => defaultApiResponse(r),
      },
    );
    await go(tester, Routes.reports);
    await tester.tap(find.byKey(const Key('openings-r-1')));
    await tester.pumpAndSettle();
    expect(find.text('The medical committee'), findsOneWidget);
    expect(
      find.text('Your file was referred to a specialist in Cardiology'),
      findsOneWidget,
    );
    expect(
      find.text('Civil Protection doctor, gouvernorat of Sfax'),
      findsOneWidget,
    );
    expect(find.textContaining('Dr '), findsNothing);
    await unmountApp(tester);
  });
}
