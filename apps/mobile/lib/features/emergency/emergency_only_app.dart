import 'package:flutter/material.dart';

import '../../core/ui/theme.dart';
import '../../l10n/app_localizations.dart';
import 'emergency_screen.dart';

/// Degraded mode when the encrypted storage cannot be opened: the app still dials the
/// emergency numbers (they need neither storage nor network).
class EmergencyOnlyApp extends StatelessWidget {
  const EmergencyOnlyApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
    onGenerateTitle: (context) => AppLocalizations.of(context).appTitle,
    debugShowCheckedModeBanner: false,
    supportedLocales: AppLocalizations.supportedLocales,
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    theme: buildTheme(Brightness.light),
    darkTheme: buildTheme(Brightness.dark),
    home: const EmergencyScreen(),
  );
}
