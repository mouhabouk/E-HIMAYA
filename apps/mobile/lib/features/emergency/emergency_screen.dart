import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/routing/app_router.dart';
import '../../core/ui/language_bar.dart';
import '../../l10n/app_localizations.dart';
import 'dialer.dart';
import 'emergency_numbers.dart';

/// Scenario 0: dial an emergency service over the SIM. Works offline, never calls the API, and
/// is reachable even before the charter is accepted.
///
/// Phase B1 makes it the emergency hub: below the numbers, the guide (topics and items) kept
/// offline. [showHub] is false in the degraded mode, which has neither router nor storage.
class EmergencyScreen extends ConsumerWidget {
  const EmergencyScreen({super.key, this.showHub = true});

  final bool showHub;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final dial = ref.watch(dialerProvider);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.emergencyTitle),
        actions: const [LanguageMenuAction()],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(l10n.emergencyIntro, style: theme.textTheme.bodyLarge),
            const SizedBox(height: 16),
            for (final n in emergencyNumbers)
              Card(
                child: Semantics(
                  button: true,
                  label: l10n.emergencyCallSemantics(n.label(l10n), n.number),
                  excludeSemantics: true,
                  child: ListTile(
                    key: Key('dial-${n.number}'),
                    minTileHeight: 72,
                    leading: Icon(
                      n.icon,
                      size: 32,
                      color: theme.colorScheme.error,
                    ),
                    title: Text(n.label(l10n)),
                    trailing: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          n.number,
                          // Phone numbers always read left-to-right.
                          textDirection: TextDirection.ltr,
                          style: theme.textTheme.headlineSmall?.copyWith(
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        const SizedBox(width: 12),
                        const Icon(Icons.call),
                      ],
                    ),
                    onTap: () async {
                      final ok = await dial(n.telUri);
                      if (!ok && context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text(l10n.dialFailed)),
                        );
                      }
                    },
                  ),
                ),
              ),
            if (showHub) ...[
              const SizedBox(height: 16),
              Card(
                child: ListTile(
                  key: const Key('hub-guide'),
                  minTileHeight: 72,
                  leading: Icon(
                    Icons.medical_services,
                    size: 32,
                    color: theme.colorScheme.primary,
                  ),
                  title: Text(l10n.guideTitle),
                  subtitle: Text(l10n.guideHubHint),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => context.push(Routes.guide),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
