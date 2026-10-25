import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/auth/identity.dart';
import '../../core/config/providers.dart';
import '../../core/http/api_error.dart';
import '../../core/http/error_messages.dart';
import '../../core/routing/app_router.dart';
import '../../core/ui/components.dart';
import '../../core/ui/emergency_action.dart';
import '../../core/ui/theme.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';
import 'safety_models.dart';
import 'safety_providers.dart';
import 'safety_reminders.dart';
import 'safety_widgets.dart';

ReminderTexts reminderTexts(AppLocalizations l10n) => (
  title: l10n.safetyCheckTitle,
  tenMinutes: l10n.safetyCheckReminder10,
  oneMinute: l10n.safetyCheckReminder1,
);

/// Addition 8.1: the user sets a time; without "I am fine" by then, the server alerts the linked
/// contacts with the last position, even if the phone is off. The operations room is not told.
class SafetyCheckScreen extends ConsumerStatefulWidget {
  const SafetyCheckScreen({super.key});

  @override
  ConsumerState<SafetyCheckScreen> createState() => _SafetyCheckScreenState();
}

class _SafetyCheckScreenState extends ConsumerState<SafetyCheckScreen> {
  int _minutes = 60;
  final _message = TextEditingController();
  bool _busy = false;
  Timer? _tick;
  String? _positionSentFor;

  @override
  void initState() {
    super.initState();
    _tick = Timer.periodic(const Duration(seconds: 30), (_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    _tick?.cancel();
    _message.dispose();
    super.dispose();
  }

  Future<void> _run(Future<void> Function() action) async {
    final l10n = AppLocalizations.of(context);
    setState(() => _busy = true);
    try {
      await action();
    } on ApiException catch (e) {
      if (mounted) showSafetySnack(context, apiErrorMessage(l10n, e.code));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final registered = ref.watch(identityProvider).isRegistered;
    final check = ref.watch(safetyCheckProvider);
    final links = ref.watch(safetyLinksProvider).value ?? const [];
    final actions = ref.read(safetyCheckActionsProvider);
    final current = check.value;
    if (current != null && current.active && _positionSentFor != current.id) {
      _positionSentFor = current.id;
      unawaited(actions.updatePosition(current));
    }
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.safetyCheckTitle),
        actions: const [StandardAppBarActions()],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(l10n.safetyCheckIntro, style: theme.textTheme.bodyLarge),
            const SizedBox(height: 16),
            if (!registered)
              SafetyRegistrationCard(reason: l10n.safetyCheckNeedsAccount)
            else if (check.isLoading && current == null)
              const Center(child: CircularProgressIndicator())
            else if (check.hasError)
              SafetyError(
                error: check.error!,
                onRetry: () => ref.invalidate(safetyCheckProvider),
              )
            else if (current != null && current.active) ...[
              Card(
                color: sosRed.withValues(alpha: 0.08),
                child: ListTile(
                  key: const Key('check-running'),
                  leading: const Icon(Icons.timer, color: sosRed),
                  title: Text(
                    l10n.safetyCheckDue(safetyTime(context, current.dueAt)),
                  ),
                  subtitle: Text(
                    [
                      l10n.safetyLiveLeft(
                        safetyDuration(
                          l10n,
                          current.dueAt.difference(ref.read(clockProvider)()),
                        ),
                      ),
                      l10n.safetyCheckContacts(current.contacts),
                    ].join(' · '),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              FilledButton.icon(
                key: const Key('check-ok'),
                style: FilledButton.styleFrom(
                  backgroundColor: BrandColors.green,
                  foregroundColor: Colors.white,
                  minimumSize: const Size.fromHeight(72),
                ),
                onPressed: _busy ? null : () => _run(() => actions.ok(current)),
                icon: const Icon(Icons.check_circle, size: 32),
                label: Text(l10n.safetyCheckOk),
              ),
              const SizedBox(height: 8),
              OutlinedButton.icon(
                key: const Key('check-extend'),
                onPressed: _busy
                    ? null
                    : () => _run(
                        () => actions.extend(current, 30, reminderTexts(l10n)),
                      ),
                icon: const Icon(Icons.more_time),
                label: Text(l10n.safetyCheckExtend(30)),
              ),
            ] else ...[
              if (current != null &&
                  current.status == 'fired' &&
                  ref.read(clockProvider)().difference(current.dueAt) <
                      const Duration(hours: 24))
                Card(
                  color: theme.colorScheme.errorContainer,
                  child: ListTile(
                    key: const Key('check-fired'),
                    title: Text(l10n.safetyCheckFired),
                    subtitle: Text(l10n.safetyCheckFiredHint),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => context.push(Routes.safetySend),
                  ),
                ),
              if (links.isEmpty)
                NavCard(
                  key: const Key('check-no-links'),
                  icon: Icons.link_rounded,
                  tone: Tone.teal,
                  title: l10n.safetyCheckNoLinks,
                  onTap: () => context.push(Routes.safetyLinked),
                ),
              const SizedBox(height: 8),
              Text(l10n.safetyCheckIn, style: theme.textTheme.titleSmall),
              Wrap(
                spacing: 8,
                children: [
                  for (final m in SafetyRules.checkMinutes)
                    ChoiceChip(
                      key: Key('check-minutes-$m'),
                      label: Text(safetyDuration(l10n, Duration(minutes: m))),
                      selected: _minutes == m,
                      onSelected: (_) => setState(() => _minutes = m),
                    ),
                ],
              ),
              const SizedBox(height: 8),
              TextField(
                key: const Key('check-message'),
                controller: _message,
                maxLength: SafetyRules.messageMax,
                maxLines: 3,
                minLines: 1,
                decoration: InputDecoration(
                  labelText: l10n.safetyCheckMessage,
                  hintText: l10n.safetyCheckMessageHint,
                ),
              ),
              FilledButton.icon(
                key: const Key('check-start'),
                style: FilledButton.styleFrom(
                  minimumSize: const Size.fromHeight(56),
                ),
                onPressed: _busy || links.isEmpty
                    ? null
                    : () => _run(
                        () => actions.start(
                          minutes: _minutes,
                          message: _message.text.trim().isEmpty
                              ? l10n.safetyCheckMessageHint
                              : _message.text.trim(),
                          texts: reminderTexts(l10n),
                        ),
                      ),
                icon: const Icon(Icons.timer),
                label: Text(l10n.safetyCheckStart),
              ),
              const SizedBox(height: 8),
              Text(l10n.safetyCheckPrivacy, style: theme.textTheme.bodySmall),
            ],
          ],
        ),
      ),
    );
  }
}
