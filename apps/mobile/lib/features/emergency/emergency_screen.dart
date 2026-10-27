import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/auth/identity.dart';
import '../../core/routing/app_router.dart';
import '../../core/ui/components.dart';
import '../../core/ui/language_bar.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';
import 'dialer.dart';
import 'emergency_numbers.dart';

/// Scenario 0: dial an emergency service over the SIM. Works offline, never calls the API, and
/// is reachable even before the charter is accepted.
///
/// Phase B1 makes it the emergency hub: below the numbers, the guide (topics and items) kept
/// offline, and the nearest places with the user's coordinates. [showHub] is false in the degraded mode, which has neither router nor storage.
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
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 5),
                child: Semantics(
                  button: true,
                  label: l10n.emergencyCallSemantics(n.label(l10n), n.number),
                  excludeSemantics: true,
                  child: AppCard(
                    key: Key('dial-${n.number}'),
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 14,
                    ),
                    onTap: () async {
                      final ok = await dial(n.telUri);
                      if (!ok && context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text(l10n.dialFailed)),
                        );
                      }
                    },
                    child: Row(
                      children: [
                        IconTile(n.icon, tone: Tone.red),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            n.label(l10n),
                            style: theme.textTheme.titleMedium?.copyWith(
                              fontSize: 16,
                            ),
                          ),
                        ),
                        Text(
                          n.number,
                          // Phone numbers always read left-to-right.
                          textDirection: TextDirection.ltr,
                          style: theme.textTheme.headlineSmall?.copyWith(
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        const SizedBox(width: 12),
                        const IconTile(
                          Icons.call_rounded,
                          tone: Tone.green,
                          size: 40,
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            if (showHub) ...[
              const SizedBox(height: 16),
              NavCard(
                key: const Key('hub-guide'),
                icon: Icons.medical_services_rounded,
                tone: Tone.green,
                title: l10n.guideTitle,
                subtitle: l10n.guideHubHint,
                onTap: () => context.push(Routes.guide),
              ),
              NavCard(
                key: const Key('hub-nearest'),
                icon: Icons.near_me_rounded,
                tone: Tone.teal,
                title: l10n.nearestTitle,
                subtitle: l10n.nearestHint,
                onTap: () => context.push(Routes.nearest),
              ),
              // Phase L1b: today's colour of the beaches (drowning risk) and why.
              NavCard(
                key: const Key('hub-beaches'),
                icon: Icons.beach_access_rounded,
                tone: Tone.sky,
                title: l10n.beachesTitle,
                subtitle: l10n.beachesHint,
                onTap: () => context.push(Routes.beaches),
              ),
              // Phase B2: personal safety (contacts, SOS message, medical file), once the
              // first-launch steps are done (before them the hub shows only what needs no setup).
              if (ref.watch(identityProvider).hasIdentity)
                NavCard(
                  key: const Key('hub-safety'),
                  icon: Icons.shield_rounded,
                  tone: Tone.navy,
                  title: l10n.safetyTitle,
                  subtitle: l10n.safetySettingsHint,
                  onTap: () => context.push(Routes.safety),
                ),
            ],
          ],
        ),
      ),
    );
  }
}
