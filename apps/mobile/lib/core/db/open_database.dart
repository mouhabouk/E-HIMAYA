import 'dart:io';
import 'dart:math';

import 'package:drift/native.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

import '../storage/secure_store.dart';
import 'app_database.dart';

/// Raised when the linked SQLite has no SQLCipher support: the queue must never be written in
/// clear text, so the app refuses to open it.
class EncryptionUnavailable implements Exception {
  const EncryptionUnavailable();
}

/// 32 random bytes, hex-encoded, generated once and kept in the platform keystore.
Future<String> loadOrCreateDatabaseKey(
  SecureStore store, {
  Random? random,
}) async {
  final existing = await store.read(SecureStoreKeys.dbKey);
  if (existing != null && RegExp(r'^[0-9a-f]{64}$').hasMatch(existing)) {
    return existing;
  }
  final rnd = random ?? Random.secure();
  final key = List<int>.generate(
    32,
    (_) => rnd.nextInt(256),
  ).map((b) => b.toRadixString(16).padLeft(2, '0')).join();
  await store.write(SecureStoreKeys.dbKey, key);
  return key;
}

/// Opens the SQLCipher-encrypted queue in a background isolate.
Future<AppDatabase> openEncryptedDatabase(SecureStore store) async {
  final hexKey = await loadOrCreateDatabaseKey(store);
  final dir = await getApplicationSupportDirectory();
  final file = File(p.join(dir.path, 'ehimaya_queue.db'));
  final executor = NativeDatabase.createInBackground(
    file,
    setup: (db) {
      // SQLCipher raw key syntax: no KDF round on a key that is already random.
      db.execute("PRAGMA key = \"x'$hexKey'\";");
      final cipher = db.select('PRAGMA cipher_version;');
      if (cipher.isEmpty) throw const EncryptionUnavailable();
      db.execute('PRAGMA cipher_memory_security = ON;');
    },
  );
  final db = AppDatabase(executor);
  try {
    // The executor opens lazily: force it now so a missing SQLCipher fails at start-up.
    await db.customSelect('SELECT 1').get();
  } on Object {
    await db.close();
    rethrow;
  }
  return db;
}

/// Overridden in `main()` with the opened database, in tests with `NativeDatabase.memory()`.
final databaseProvider = Provider<AppDatabase>(
  (ref) => throw UnimplementedError('databaseProvider not overridden'),
);

/// Helper for tests and tools: an unencrypted in-memory database.
AppDatabase inMemoryDatabase() => AppDatabase(NativeDatabase.memory());
