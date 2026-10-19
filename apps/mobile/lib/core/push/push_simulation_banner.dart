// ┏━━ SIMULATION ━━ Amber "Simulation mode" banner shown while pushes come from notify-sim.
// ┃ PRODUCTION: nothing to remove: it renders nothing unless the build was made with
// ┃   --dart-define=PUSH_SIMULATOR_URL and without the FIREBASE_* defines (see
// ┃   simulated_push_messaging.dart and apps/mobile/README.md, "Switching to production").
// ┗━━━━━━━━━━━━━━━━
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../l10n/app_localizations.dart';
import 'push_messaging.dart';

/// Warns that notifications are simulated, so a test run is never taken for real delivery.
/// Amber in both themes (dark text on amber keeps the contrast).
class PushSimulationBanner extends ConsumerWidget {
  const PushSimulationBanner({super.key});

  static const _background = Color(0xFFFFB300); // amber 600
  static const _foreground = Color(0xFF3E2723);

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (!ref.watch(pushSimulationActiveProvider)) {
      return const SizedBox.shrink();
    }
    final l10n = AppLocalizations.of(context);
    final text = Theme.of(context).textTheme;
    return Semantics(
      container: true,
      liveRegion: true,
      child: Container(
        key: const Key('push-simulation-banner'),
        margin: const EdgeInsetsDirectional.fromSTEB(16, 12, 16, 4),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: _background,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Icon(Icons.science_outlined, color: _foreground),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    l10n.pushSimulationBadge,
                    style: text.titleSmall?.copyWith(
                      color: _foreground,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    l10n.pushSimulationHelp,
                    style: text.bodySmall?.copyWith(color: _foreground),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
