// covers: phase C1-b (docs/phase-c/design-medical-axis.md §12): the phone locks, the doctor opens.
import 'dart:convert';

import 'package:ehimaya/core/crypto/medical_crypto.dart';
import 'package:flutter_test/flutter_test.dart';

// Made by services/api/tests/medical_crypto.py with the private key 00 01 02 … 1f: the app and the
// reference agree on the format.
const _publicKey = 'j0DFrbaPJWJK5bIU6nZ6bslNgp09e14a0bpvPiE4KF8=';
const _opened = <String, Object?>{
  'nonce': 'YXEwdh0uwmwCycUO',
  'ciphertext': 'ZysKJHcjre7NuqlKJHQOJt918tE6eNcYl2VyiMkxvR8lVL8/C7tuPCBxwwmmO9pWduJi5J4sICjl5ePXHGL5sczmtTftppBc0A==',
  'eph_public': '/e4H227C6kwXS3cybUy4NFwPyfJpBghhzIvkSIXD1Bo=',
  'key_nonce': 'lEcmkiYvK/AGhpNl',
  'wrapped': 'FhEubSLgukgMHXgurNN2z7T0rownMe/YKPwTf50cdquwZR5AVj9RnSkpO9U1VfC0',
};
const _backup = <String, Object?>{
  'kdf': 'argon2id',
  'memory_kib': 8192,
  'iterations': 1,
  'parallelism': 1,
  'salt': 'p9HGGhIZppmf2MuSlYGUSA==',
  'nonce': 'FHT2VgJD3mA4OISh',
  'ciphertext':
      'MajKx0Qork5EnEHQhnhClZBB/w4QYOH+w/Ispsx+47TC03BeMcKqwz4nMWnjtqoA',
};

void main() {
  final crypto = MedicalCrypto(
    kdf: const KdfParams(memoryKib: 8192, iterations: 1),
  );

  test('opens a file locked by the reference implementation', () async {
    final key = await DoctorKeyPair.fromPrivate(List.generate(32, (i) => i));
    expect(base64.encode(key.publicKey), _publicKey);
    expect(await crypto.open(_opened, key), {
      'conditions': 'diabète',
      'medications': 'insuline',
    });
  });

  test(
    'restores the reference backup with the code, refuses a wrong code',
    () async {
      final key = await crypto.restore(_backup, '482916');
      expect(base64.encode(key.publicKey), _publicKey);
      await expectLater(
        crypto.restore(_backup, '000000'),
        throwsA(isA<WrongCodeException>()),
      );
    },
  );

  test('locks for each doctor; only they open it', () async {
    final a = await crypto.newKey();
    final b = await crypto.newKey();
    final stranger = await crypto.newKey();
    final locked = await crypto.lock(
      {'other': 'pacemaker'},
      {'a': a.publicKey, 'b': b.publicKey},
    );
    expect(
      utf8.decode(
        base64.decode(locked['ciphertext']! as String),
        allowMalformed: true,
      ),
      isNot(contains('pacemaker')),
    );
    final keys = (locked['keys']! as List).cast<Map<String, Object?>>();
    Map<String, Object?> copyFor(String id) {
      final k = keys.firstWhere((k) => k['doctor_id'] == id);
      return {
        'nonce': locked['nonce'],
        'ciphertext': locked['ciphertext'],
        'eph_public': k['eph_public'],
        'key_nonce': k['nonce'],
        'wrapped': k['wrapped'],
      };
    }

    expect(await crypto.open(copyFor('a'), a), {'other': 'pacemaker'});
    expect(await crypto.open(copyFor('b'), b), {'other': 'pacemaker'});
    await expectLater(crypto.open(copyFor('a'), stranger), throwsA(anything));
    // A new key backed up and restored with its code.
    final saved = await crypto.backup(a, '7391');
    expect((await crypto.restore(saved, '7391')).publicKey, a.publicKey);
  });
}
