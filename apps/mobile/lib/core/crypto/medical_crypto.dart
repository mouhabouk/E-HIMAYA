import 'dart:convert';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:cryptography/dart.dart';

/// Locked medical files (phase C1-b, docs/phase-c/design-medical-axis.md §12). The same format as
/// services/api/tests/medical_crypto.py:
///
/// * file: AES-256-GCM with a random 32-byte key (DEK), 12-byte nonce, no associated data;
/// * key for one doctor: ephemeral X25519 with the doctor's public key, HKDF-SHA256 (salt =
///   ephemeral public key ‖ doctor public key, info = `ehimaya-medical-v1`, 32 bytes), then
///   AES-256-GCM of the DEK (48 bytes);
/// * the doctor's backup: Argon2id of their code (16-byte salt), then AES-256-GCM of the 32-byte
///   private key.
///
/// The server keeps the results and can open none of them.
class MedicalCrypto {
  MedicalCrypto({this.kdf = const KdfParams(), this.isolates = true});

  final KdfParams kdf;

  /// Argon2id runs in a background isolate so the screen stays responsive. Widget tests turn it
  /// off: their fake clock never delivers an isolate's answer.
  final bool isolates;

  static final _aes = AesGcm.with256bits();
  static final _x25519 = X25519();
  static final _hkdf = Hkdf(hmac: Hmac.sha256(), outputLength: 32);
  static const _info = 'ehimaya-medical-v1';

  /// Locks [data] for each recipient (`doctor_id` → raw public key): the body of
  /// `medical_locked`.
  Future<Map<String, Object?>> lock(
    Map<String, Object?> data,
    Map<String, List<int>> recipients,
  ) async {
    final dek = await _aes.newSecretKey();
    final dekBytes = await dek.extractBytes();
    final box = await _aes.encrypt(
      utf8.encode(jsonEncode(data)),
      secretKey: dek,
    );
    final keys = <Map<String, Object?>>[];
    for (final MapEntry(key: doctorId, value: doctorPublic)
        in recipients.entries) {
      final eph = await _x25519.newKeyPair();
      final ephPublic = (await eph.extractPublicKey()).bytes;
      final shared = await _x25519.sharedSecretKey(
        keyPair: eph,
        remotePublicKey: SimplePublicKey(
          doctorPublic,
          type: KeyPairType.x25519,
        ),
      );
      final kek = await _hkdf.deriveKey(
        secretKey: shared,
        nonce: [...ephPublic, ...doctorPublic],
        info: utf8.encode(_info),
      );
      final wrapped = await _aes.encrypt(dekBytes, secretKey: kek);
      keys.add({
        'doctor_id': doctorId,
        'eph_public': base64.encode(ephPublic),
        'nonce': base64.encode(wrapped.nonce),
        'wrapped': base64.encode([...wrapped.cipherText, ...wrapped.mac.bytes]),
      });
    }
    return {
      'nonce': base64.encode(box.nonce),
      'ciphertext': base64.encode([...box.cipherText, ...box.mac.bytes]),
      'keys': keys,
    };
  }

  /// Opens the doctor's copy (`POST /api/v1/medical/files/{id}/open`) with their private key.
  Future<Map<String, Object?>> open(
    Map<String, Object?> opened,
    DoctorKeyPair key,
  ) async {
    final ephPublic = base64.decode(opened['eph_public']! as String);
    final shared = await _x25519.sharedSecretKey(
      keyPair: key.keyPair,
      remotePublicKey: SimplePublicKey(ephPublic, type: KeyPairType.x25519),
    );
    final kek = await _hkdf.deriveKey(
      secretKey: shared,
      nonce: [...ephPublic, ...key.publicKey],
      info: utf8.encode(_info),
    );
    final dek = await _aes.decrypt(
      _box(opened['key_nonce']! as String, opened['wrapped']! as String),
      secretKey: kek,
    );
    final plain = await _aes.decrypt(
      _box(opened['nonce']! as String, opened['ciphertext']! as String),
      secretKey: SecretKey(dek),
    );
    return (jsonDecode(utf8.decode(plain)) as Map).cast<String, Object?>();
  }

  /// A new personal key for a verified doctor.
  Future<DoctorKeyPair> newKey() async =>
      DoctorKeyPair.from(await _x25519.newKeyPair());

  /// The private key locked by the doctor's [code] (`PUT /api/v1/me/doctor/key`, `backup`).
  Future<Map<String, Object?>> backup(DoctorKeyPair key, String code) async {
    final salt = SecretKeyData.random(length: 16).bytes;
    final kek = await _argon(kdf, salt, code, isolates: isolates);
    final box = await _aes.encrypt(key.privateKey, secretKey: kek);
    return {
      'kdf': 'argon2id',
      'memory_kib': kdf.memoryKib,
      'iterations': kdf.iterations,
      'parallelism': kdf.parallelism,
      'salt': base64.encode(salt),
      'nonce': base64.encode(box.nonce),
      'ciphertext': base64.encode([...box.cipherText, ...box.mac.bytes]),
    };
  }

  /// The private key back from its backup; throws [WrongCodeException] for a wrong code.
  Future<DoctorKeyPair> restore(Map<String, Object?> saved, String code) async {
    final params = KdfParams(
      memoryKib: (saved['memory_kib']! as num).toInt(),
      iterations: (saved['iterations']! as num).toInt(),
      parallelism: (saved['parallelism']! as num).toInt(),
    );
    final kek = await _argon(
      params,
      base64.decode(saved['salt']! as String),
      code,
      isolates: isolates,
    );
    try {
      final secret = await _aes.decrypt(
        _box(saved['nonce']! as String, saved['ciphertext']! as String),
        secretKey: kek,
      );
      return await DoctorKeyPair.fromPrivate(secret);
    } on SecretBoxAuthenticationError {
      throw const WrongCodeException();
    }
  }

  static Future<SecretKey> _argon(
    KdfParams p,
    List<int> salt,
    String code, {
    required bool isolates,
  }) => DartArgon2id(
    memory: p.memoryKib,
    iterations: p.iterations,
    parallelism: p.parallelism,
    hashLength: 32,
    maxIsolates: isolates ? null : 0,
  ).deriveKey(secretKey: SecretKey(utf8.encode(code)), nonce: salt);

  static SecretBox _box(String nonce, String sealed) {
    final bytes = base64.decode(sealed);
    return SecretBox(
      bytes.sublist(0, bytes.length - 16),
      nonce: base64.decode(nonce),
      mac: Mac(bytes.sublist(bytes.length - 16)),
    );
  }
}

/// Argon2id cost of the doctor's backup. The default suits a phone (about a second).
class KdfParams {
  const KdfParams({
    this.memoryKib = 19456,
    this.iterations = 2,
    this.parallelism = 1,
  });

  final int memoryKib;
  final int iterations;
  final int parallelism;
}

class WrongCodeException implements Exception {
  const WrongCodeException();
}

/// A doctor's X25519 key pair as raw bytes (kept in the phone's secure storage).
class DoctorKeyPair {
  DoctorKeyPair._(this.keyPair, this.privateKey, this.publicKey);

  final SimpleKeyPair keyPair;
  final Uint8List privateKey;
  final Uint8List publicKey;

  static Future<DoctorKeyPair> from(SimpleKeyPair pair) async =>
      DoctorKeyPair._(
        pair,
        Uint8List.fromList(await pair.extractPrivateKeyBytes()),
        Uint8List.fromList((await pair.extractPublicKey()).bytes),
      );

  static Future<DoctorKeyPair> fromPrivate(List<int> privateKey) async =>
      from(await X25519().newKeyPairFromSeed(privateKey));
}
