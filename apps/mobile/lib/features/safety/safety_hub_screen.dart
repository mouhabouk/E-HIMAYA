import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/routing/app_router.dart';
import '../../core/ui/components.dart';
import '../../core/ui/emergency_action.dart';
import '../../core/ui/theme.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';
import 'safety_providers.dart';

/// Phase B2: personal safety, from the settings and the emergency hub. Everything that can stay
/// on the phone does (contacts, groups, the message, the medical file, the recent list).
class SafetyHubScreen extends ConsumerWidget {
  const SafetyHubScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final contacts = ref.watch(emergencyContactsProvider).value ?? const [];
    final links = ref.watch(safetyLinksProvider).value ?? const [];
    final live = ref.watch(liveShareProvider);
    final check = ref.watch(safetyCheckProvider).value;
    final history = ref.watch(locationHistoryProvider).value;
    final medical = ref.watch(medicalRowProvider).value;

    Widget tile({
      required String key,
      required IconData icon,
      required String title,
      String? subtitle,
      required String route,
      Tone tone = Tone.green,
    }) => NavCard(
      key: Key(key),
      icon: icon,
      tone: tone,
      title: title,
      subtitle: subtitle,
      onTap: () => context.push(route),
    );

    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.safetyTitle),
        actions: const [StandardAppBarActions()],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(l10n.safetyIntro, style: theme.textTheme.bodyLarge),
            const SizedBox(height: 16),
            FilledButton.icon(
              key: const Key('safety-send-sos'),
              style: FilledButton.styleFrom(
                backgroundColor: sosRed,
                foregroundColor: Colors.white,
                minimumSize: const Size.fromHeight(60),
              ),
              onPressed: () => context.push(Routes.safetySend),
              icon: const Icon(Icons.sms_failed),
              label: Text(l10n.safetySendSos),
            ),
            const SizedBox(height: 16),
            tile(
              key: 'safety-contacts',
              icon: Icons.contacts_rounded,
              tone: Tone.navy,
              title: l10n.safetyContactsTitle,
              subtitle: l10n.safetyContactsCount(contacts.length),
              route: Routes.safetyContacts,
            ),
            tile(
              key: 'safety-message',
              icon: Icons.edit_note_rounded,
              tone: Tone.slate,
              title: l10n.safetyMessageTitle,
              subtitle: l10n.safetyMessageHint,
              route: Routes.safetyMessage,
            ),
            tile(
              key: 'safety-linked',
              icon: Icons.link_rounded,
              tone: Tone.teal,
              title: l10n.safetyLinkedTitle,
              subtitle: l10n.safetyLinkedCount(links.length),
              route: Routes.safetyLinked,
            ),
            tile(
              key: 'safety-live',
              icon: Icons.share_location_rounded,
              title: l10n.safetyLiveTitle,
              subtitle: live == null
                  ? l10n.safetyLiveHint
                  : l10n.safetyLiveRunning,
              route: Routes.safetyLive,
              tone: live == null ? Tone.teal : Tone.red,
            ),
            tile(
              key: 'safety-check',
              icon: Icons.timer_rounded,
              title: l10n.safetyCheckTitle,
              subtitle: check?.active == true
                  ? l10n.safetyCheckRunning
                  : l10n.safetyCheckHint,
              route: Routes.safetyCheck,
              tone: check?.active == true ? Tone.red : Tone.amber,
            ),
            tile(
              key: 'safety-medical',
              icon: Icons.medical_information_rounded,
              tone: Tone.purple,
              title: l10n.safetyMedicalTitle,
              subtitle: medical == null
                  ? l10n.safetyMedicalHint
                  : l10n.safetyMedicalSaved,
              route: Routes.safetyMedical,
            ),
            tile(
              key: 'safety-test',
              icon: Icons.fact_check_rounded,
              title: l10n.safetyTestTitle,
              subtitle: l10n.safetyTestHint,
              route: Routes.safetyTest,
            ),
            tile(
              key: 'safety-recent',
              icon: Icons.history_rounded,
              tone: Tone.slate,
              title: l10n.safetyRecentTitle,
              route: Routes.safetyRecent,
            ),
            // Hidden while the platform keeps it off (legal review, design-b2 §9).
            if (history != null && history.available)
              tile(
                key: 'safety-location-history',
                icon: Icons.route_rounded,
                tone: Tone.teal,
                title: l10n.safetyHistoryTitle,
                subtitle: history.enabled
                    ? l10n.safetyHistoryOn
                    : l10n.safetyHistoryOff,
                route: Routes.safetyLocationHistory,
              ),
          ],
        ),
      ),
    );
  }
}
