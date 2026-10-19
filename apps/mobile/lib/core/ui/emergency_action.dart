import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../l10n/app_localizations.dart';
import '../routing/app_router.dart';

/// App-bar action present on every screen: opens the emergency numbers (offline, no API).
class EmergencyNumbersAction extends StatelessWidget {
  const EmergencyNumbersAction({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return IconButton(
      key: const Key('emergency-numbers-action'),
      tooltip: l10n.emergencyTitle,
      icon: const Icon(Icons.phone_in_talk),
      onPressed: () => context.push(Routes.emergency),
    );
  }
}
