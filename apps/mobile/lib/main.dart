import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'app.dart';
import 'core/auth/identity.dart';
import 'core/db/app_database.dart';
import 'core/db/open_database.dart';
import 'core/logging/log.dart';
import 'core/push/push_controller.dart';
import 'core/push/push_messaging.dart';
import 'core/storage/app_prefs.dart';
import 'core/storage/secure_store.dart';
import 'core/sync/sync_scheduler.dart';
import 'features/alerts/alerts_providers.dart';
import 'features/emergency/emergency_only_app.dart';
import 'features/volunteer/volunteer_providers.dart';
import 'l10n/app_localizations.dart';

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
  container.read(alertsSchedulerProvider).start();
  container.read(readinessTrackerProvider).start();
  // Push is optional: without Firebase on this build the app polls the active alerts.
  unawaited(
    container
        .read(pushControllerProvider)
        .start(_channelNames(container.read(appPrefsProvider).localeCode)),
  );

  runApp(
    UncontrolledProviderScope(container: container, child: const EHimayaApp()),
  );
}

/// Android channel names, in the language chosen in the app (Arabic by default).
PushChannelNames _channelNames(String? code) {
  final l10n = lookupAppLocalizations(
    Locale(const ['ar', 'fr', 'en'].contains(code) ? code! : 'ar'),
  );
  return PushChannelNames(
    alerts: l10n.channelAlerts,
    alertsDescription: l10n.channelAlertsDesc,
    general: l10n.channelGeneral,
    generalDescription: l10n.channelGeneralDesc,
  );
}
