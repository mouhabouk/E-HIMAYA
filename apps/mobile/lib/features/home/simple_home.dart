import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/a11y/simple_mode.dart';
import '../../core/routing/app_router.dart';
import '../../core/ui/emergency_action.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';
import '../alerts/alerts_providers.dart';
import '../alerts/notifications_screen.dart';
import '../emergency/dialer.dart';
import '../emergency/emergency_numbers.dart';
import '../sos/sos_widgets.dart';

/// Simplified home (phase P5b, F-APP-142): five large buttons in short, plain sentences, low on
/// the screen within reach of the thumb, the SOS button right below them. "Show all options"
/// brings the full home back; the settings switch does the same.
class SimpleHomeScreen extends ConsumerWidget {
  const SimpleHomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final alertsCount = ref.watch(currentAlertsProvider).length;
    final civil = emergencyNumbers.first;
    return Scaffold(
      appBar: AppBar(
        title: Text(
          l10n.appTitle,
          style: const TextStyle(fontWeight: FontWeight.w800),
        ),
        actions: const [StandardAppBarActions()],
      ),
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, box) => SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: ConstrainedBox(
              constraints: BoxConstraints(minHeight: box.maxHeight - 32),
              child: Column(
                // One hand: the actions gather at the bottom, near the thumb.
                mainAxisAlignment: MainAxisAlignment.end,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const HighAlertsBanner(),
                  _BigAction(
                    key: const Key('simple-alerts'),
                    icon: Icons.campaign_rounded,
                    tone: Tone.sky,
                    label: l10n.simpleAlerts,
                    count: alertsCount,
                    onTap: () => context.push(Routes.notifications),
                  ),
                  _BigAction(
                    key: const Key('simple-what-to-do'),
                    icon: Icons.medical_services_rounded,
                    tone: Tone.green,
                    label: l10n.simpleWhatToDo,
                    onTap: () => context.push(Routes.emergency),
                  ),
                  _BigAction(
                    key: const Key('simple-sos-message'),
                    icon: Icons.sms_rounded,
                    tone: Tone.purple,
                    label: l10n.simpleSosMessage,
                    onTap: () => context.push(Routes.safetySend),
                  ),
                  _BigAction(
                    key: const Key('simple-report'),
                    icon: Icons.report_rounded,
                    tone: Tone.navy,
                    label: l10n.simpleReport,
                    onTap: () => context.push(Routes.newReport),
                  ),
                  _BigAction(
                    key: const Key('simple-call-198'),
                    icon: Icons.phone_rounded,
                    tone: Tone.red,
                    label: l10n.simpleCall198,
                    onTap: () => ref.read(dialerProvider)(civil.telUri),
                  ),
                  const SizedBox(height: 12),
                  const Center(child: SosButton()),
                  const SizedBox(height: 8),
                  Text(
                    l10n.simpleSosHint,
                    textAlign: TextAlign.center,
                    style: theme.textTheme.titleMedium,
                  ),
                  const SizedBox(height: 8),
                  TextButton.icon(
                    key: const Key('simple-show-all'),
                    icon: const Icon(Icons.apps_rounded),
                    label: Text(l10n.simpleShowAll),
                    onPressed: () =>
                        ref.read(simpleModeProvider.notifier).set(false),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// A full-width button at least 88 points high: large glyph and one short sentence on the
/// category colour. The alerts count is spoken with the label.
class _BigAction extends StatelessWidget {
  const _BigAction({
    super.key,
    required this.icon,
    required this.tone,
    required this.label,
    required this.onTap,
    this.count = 0,
  });

  final IconData icon;
  final Tone tone;
  final String label;
  final VoidCallback onTap;
  final int count;

  @override
  Widget build(BuildContext context) {
    final c = tone.colors(context);
    final text = Theme.of(context).textTheme.titleLarge
        ?.copyWith(color: c.onFill, fontWeight: FontWeight.w800);
    return Padding(
      padding: const EdgeInsets.only(top: 10),
      child: Semantics(
        button: true,
        label: count > 0 ? '$label, $count' : label,
        excludeSemantics: true,
        child: Material(
          color: c.fill,
          borderRadius: BorderRadius.circular(Radii.card),
          clipBehavior: Clip.antiAlias,
          child: InkWell(
            onTap: onTap,
            child: ConstrainedBox(
              constraints: const BoxConstraints(minHeight: 88),
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 20,
                  vertical: 16,
                ),
                child: Row(
                  children: [
                    Icon(icon, size: 40, color: c.onFill),
                    const SizedBox(width: 16),
                    Expanded(child: Text(label, style: text)),
                    if (count > 0)
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 4,
                        ),
                        decoration: BoxDecoration(
                          color: c.onFill,
                          borderRadius: BorderRadius.circular(999),
                        ),
                        child: Text(
                          '$count',
                          style: text?.copyWith(color: c.fill),
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
