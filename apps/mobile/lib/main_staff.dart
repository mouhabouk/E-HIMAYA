import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'core/logging/log.dart';
import 'core/storage/app_prefs.dart';
import 'core/storage/secure_store.dart';
import 'features/live/live_controller.dart';
import 'staff/staff_api.dart';
import 'staff/staff_app.dart';
import 'staff/staff_controller.dart';

/// Entry point of the staff app (phase P4a): `flutter run --flavor staff -t lib/main_staff.dart`.
/// Same code base and design system as the citizen app; since phase P4d its own Android flavor
/// (tn.ehimaya.staff) with the mission ringing over the lock screen.
Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  configureLogging();
  final prefs = await SharedPreferences.getInstance();
  runApp(
    ProviderScope(
      overrides: [
        sharedPreferencesProvider.overrideWithValue(prefs),
        secureStoreProvider.overrideWithValue(PlatformSecureStore()),
        // Phase D: the live session streams a mission, not a report.
        liveStreamApiProvider.overrideWith(
          (ref) => CrewLiveStreamApi(ref.read(staffApiProvider)),
        ),
      ],
      child: const StaffApp(),
    ),
  );
}
