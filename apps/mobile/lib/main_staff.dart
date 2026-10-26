import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'core/logging/log.dart';
import 'core/storage/app_prefs.dart';
import 'core/storage/secure_store.dart';
import 'staff/staff_app.dart';

/// Entry point of the staff app (phase P4a): `flutter run -t lib/main_staff.dart`. Same code base
/// and design system as the citizen app; its own Android flavor and lock-screen alert come in P4c.
Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  configureLogging();
  final prefs = await SharedPreferences.getInstance();
  runApp(
    ProviderScope(
      overrides: [
        sharedPreferencesProvider.overrideWithValue(prefs),
        secureStoreProvider.overrideWithValue(PlatformSecureStore()),
      ],
      child: const StaffApp(),
    ),
  );
}
