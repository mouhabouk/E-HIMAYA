import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Key/value store backed by the platform keystore (Android Keystore, iOS Keychain).
///
/// Holds the OIDC tokens, the anonymous device key and the SQLCipher key.
abstract class SecureStore {
  Future<String?> read(String key);
  Future<void> write(String key, String value);
  Future<void> delete(String key);
}

class SecureStoreKeys {
  static const deviceKey = 'device_key_v1';
  static const dbKey = 'db_key_v1';
  static const authSession = 'auth_session_v1';
}

class PlatformSecureStore implements SecureStore {
  PlatformSecureStore()
    : _storage = const FlutterSecureStorage(
        iOptions: IOSOptions(
          accessibility: KeychainAccessibility.first_unlock_this_device,
        ),
      );

  final FlutterSecureStorage _storage;

  @override
  Future<String?> read(String key) => _storage.read(key: key);

  @override
  Future<void> write(String key, String value) =>
      _storage.write(key: key, value: value);

  @override
  Future<void> delete(String key) => _storage.delete(key: key);
}

/// In-memory implementation for tests.
class MemorySecureStore implements SecureStore {
  MemorySecureStore([Map<String, String>? initial]) : values = {...?initial};

  final Map<String, String> values;

  @override
  Future<String?> read(String key) async => values[key];

  @override
  Future<void> write(String key, String value) async => values[key] = value;

  @override
  Future<void> delete(String key) async => values.remove(key);
}

final secureStoreProvider = Provider<SecureStore>(
  (ref) => PlatformSecureStore(),
);
