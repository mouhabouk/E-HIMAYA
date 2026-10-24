import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/crypto/medical_crypto.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/storage/secure_store.dart';
import 'doctor_providers.dart';

/// Phase C1-b: the doctor's personal key (docs/phase-c/design-medical-axis.md §3, §12). The private
/// key stays in the phone's secure storage; the server keeps the public key and a copy locked by
/// the doctor's own code, so a new phone gets it back with that code. Nobody else can open it.
const doctorKeyStoreKey = 'doctor_key_v1';

/// The cost of the code's key derivation; tests use a cheaper one.
final medicalCryptoProvider = Provider<MedicalCrypto>((ref) => MedicalCrypto());

class DoctorKeyController extends AsyncNotifier<DoctorKeyPair?> {
  @override
  Future<DoctorKeyPair?> build() async {
    final raw = await ref.read(secureStoreProvider).read(doctorKeyStoreKey);
    if (raw == null) return null;
    return DoctorKeyPair.fromPrivate(base64.decode(raw));
  }

  Future<void> _keep(DoctorKeyPair key) async {
    await ref
        .read(secureStoreProvider)
        .write(doctorKeyStoreKey, base64.encode(key.privateKey));
    state = AsyncData(key);
  }

  /// A new key locked by [code] (first time, or after a forgotten code: the files locked for the
  /// old key can no longer be opened).
  Future<void> create(String code) async {
    final crypto = ref.read(medicalCryptoProvider);
    final key = await crypto.newKey();
    final backup = await crypto.backup(key, code);
    await ref
        .read(doctorProvider.notifier)
        .applyKey(base64.encode(key.publicKey), backup);
    await _keep(key);
  }

  /// The key back on this phone; throws [WrongCodeException] for a wrong code.
  Future<void> restore(String code) async {
    final saved = await ref.read(apiProvider).doctorKey();
    if (saved == null) throw StateError('no key');
    final key = await ref
        .read(medicalCryptoProvider)
        .restore(saved.backup, code);
    if (base64.encode(key.publicKey) != saved.publicKey) {
      throw const WrongCodeException();
    }
    await _keep(key);
  }

  Future<void> forget() async {
    await ref.read(secureStoreProvider).delete(doctorKeyStoreKey);
    state = const AsyncData(null);
  }
}

final doctorKeyProvider =
    AsyncNotifierProvider<DoctorKeyController, DoctorKeyPair?>(
      DoctorKeyController.new,
    );
