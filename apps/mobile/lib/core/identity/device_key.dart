import 'dart:convert';
import 'dart:math';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../storage/secure_store.dart';

/// Anonymous identity (contract §1): 32 random bytes generated once per install, base64url
/// without padding (43 characters), kept in the platform secure storage and sent as
/// `X-Device-Key`. The server only ever stores an HMAC of it.
class DeviceKeyStore {
  DeviceKeyStore(this._store, {Random? random})
    : _random = random ?? Random.secure();

  final SecureStore _store;
  final Random _random;
  Future<String>? _pending;

  static final RegExp format = RegExp(r'^[A-Za-z0-9_-]{43}$');

  /// Returns the device key, generating and persisting it on first use.
  Future<String> get() => _pending ??= _loadOrCreate();

  Future<String> _loadOrCreate() async {
    final existing = await _store.read(SecureStoreKeys.deviceKey);
    if (existing != null && format.hasMatch(existing)) return existing;
    final key = generate(_random);
    await _store.write(SecureStoreKeys.deviceKey, key);
    return key;
  }

  static String generate(Random random) {
    final bytes = List<int>.generate(32, (_) => random.nextInt(256));
    return base64Url.encode(bytes).replaceAll('=', '');
  }
}

final deviceKeyStoreProvider = Provider<DeviceKeyStore>(
  (ref) => DeviceKeyStore(ref.watch(secureStoreProvider)),
);
