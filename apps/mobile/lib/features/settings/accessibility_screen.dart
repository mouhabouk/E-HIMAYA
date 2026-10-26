import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/a11y/alert_cues.dart';
import '../../core/a11y/torch.dart';
import '../../core/ui/components.dart';
import '../../core/ui/emergency_action.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';

/// Whether this phone has a camera light (asked once per screen).
final torchAvailableProvider = FutureProvider.autoDispose<bool>(
  (ref) => ref.read(torchProvider).available(),
);

/// Phase P5a (NFR-10): the cues for deaf, hard-of-hearing and blind users, and where the
/// phone's own settings take over.
class AccessibilityScreen extends ConsumerWidget {
  const AccessibilityScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final cues = ref.watch(a11yCuesProvider);
    final controller = ref.read(a11yCuesProvider.notifier);
    final torch = ref.watch(torchAvailableProvider).value ?? false;
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.a11yTitle),
        actions: const [StandardAppBarActions()],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          SectionTitle(l10n.a11yUrgentSection),
          NavCard(
            icon: Icons.flash_on_rounded,
            tone: Tone.red,
            title: l10n.a11yScreenFlash,
            subtitle: l10n.a11yScreenFlashHelp,
            trailing: Switch(
              key: const Key('a11y-screen-flash'),
              value: cues.screenFlash,
              onChanged: controller.setScreenFlash,
            ),
          ),
          NavCard(
            icon: Icons.flashlight_on_rounded,
            tone: Tone.amber,
            title: l10n.a11yTorchFlash,
            subtitle: torch
                ? l10n.a11yTorchFlashHelp
                : l10n.a11yTorchUnavailable,
            trailing: Switch(
              key: const Key('a11y-torch-flash'),
              value: cues.torchFlash && torch,
              onChanged: torch ? controller.setTorchFlash : null,
            ),
          ),
          NavCard(
            icon: Icons.record_voice_over_rounded,
            tone: Tone.navy,
            title: l10n.a11yReadAlerts,
            subtitle: l10n.a11yReadAlertsHelp,
            trailing: Switch(
              key: const Key('a11y-read-alerts'),
              value: cues.readAlerts,
              onChanged: controller.setReadAlerts,
            ),
          ),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            key: const Key('a11y-try'),
            icon: const Icon(Icons.play_arrow_rounded),
            label: Text(l10n.a11yTry),
            onPressed: () {
              if (!cues.any) {
                ScaffoldMessenger.of(context)
                    .showSnackBar(SnackBar(content: Text(l10n.a11yTryNothing)));
                return;
              }
              unawaited(ref.read(alertCuesProvider).run(l10n.a11yTrySample));
            },
          ),
          const SizedBox(height: 12),
          Text(l10n.a11yAlwaysNote, style: theme.textTheme.bodyMedium),
          SectionTitle(l10n.a11yPhoneSection),
          Text(l10n.a11yPhoneNote, style: theme.textTheme.bodyMedium),
        ],
      ),
    );
  }
}
