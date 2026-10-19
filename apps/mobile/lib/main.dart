import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'app.dart';
import 'core/auth/identity.dart';
import 'core/db/app_database.dart';
import 'core/db/open_database.dart';
import 'core/logging/log.dart';
import 'core/storage/app_prefs.dart';
import 'core/storage/secure_store.dart';
import 'core/sync/sync_scheduler.dart';
import 'features/emergency/emergency_only_app.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  configureLogging();

  final secure = PlatformSecureStore();
  final prefs = await SharedPreferences.getInstance();
  final session = await loadStoredSession(secure);
  final AppDatabase db;
  try {
    db = await openEncryptedDatabase(secure);
  } on Object catch (e, st) {
    // Never leave the user without a way to call for help: emergency numbers only.
    logger('main').severe('encrypted queue unavailable', e, st);
    runApp(const ProviderScope(child: EmergencyOnlyApp()));
    return;
  }

  final container = ProviderContainer(
    overrides: [
      sharedPreferencesProvider.overrideWithValue(prefs),
      secureStoreProvider.overrideWithValue(secure),
      initialAuthSessionProvider.overrideWithValue(session),
      databaseProvider.overrideWithValue(db),
    ],
  );
  container.read(syncSchedulerProvider).start();

  runApp(
    UncontrolledProviderScope(container: container, child: const EHimayaApp()),
  );
}
