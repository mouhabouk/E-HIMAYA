import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/quota/anon_quota_controller.dart';
import '../../core/routing/app_router.dart';
import '../../core/sync/sync_scheduler.dart';
import '../../core/ui/emergency_action.dart';
import '../../l10n/app_localizations.dart';
import '../emergency/dialer.dart';
import '../emergency/emergency_numbers.dart';
import '../onboarding/login_actions.dart';
import 'quota_widgets.dart';

/// Anonymous report quota (phase 9 §3): why there is a limit, how many reports are left, the
/// way to an account, and the 198 call, which never depends on the quota, the network or the
/// account. [tempCode]: a report the user just submitted while the quota was exhausted; it is
/// kept on the phone (state `blocked`) and sent once the user signs in.
class AnonQuotaScreen extends ConsumerWidget {
  const AnonQuotaScreen({super.key, this.tempCode});

  final String? tempCode;

  Future<void> _signIn(
    BuildContext context,
    WidgetRef ref, {
    required bool register,
  }) async {
    final router = GoRouter.of(context);
    final requestSync = ref.read(requestSyncProvider);
    if (!await runLogin(context, ref, register: register)) return;
    // Blocked reports are resent by the next pass now that the account exists.
    unawaited(requestSync());
    router.go(tempCode == null ? Routes.home : Routes.reports);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final quota = ref.watch(anonQuotaProvider);
    final civil = emergencyNumbers.first;
    final code = tempCode;
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.anonQuotaTitle),
        actions: const [StandardAppBarActions()],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            Icon(
              quota?.exhausted ?? false
                  ? Icons.lock_outline
                  : Icons.person_outline,
              size: 56,
              color: theme.colorScheme.primary,
            ),
            if (quota != null) ...[
              const SizedBox(height: 12),
              Text(
                anonQuotaLabel(l10n, quota),
                key: const Key('anon-quota-screen-label'),
                textAlign: TextAlign.center,
                style: theme.textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
            if (code != null && code.isNotEmpty) ...[
              const SizedBox(height: 16),
              Card(
                color: theme.colorScheme.tertiaryContainer,
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Text(
                    l10n.anonQuotaDraftKept(code),
                    key: const Key('anon-quota-draft-kept'),
                    textAlign: TextAlign.center,
                  ),
                ),
              ),
            ],
            const SizedBox(height: 24),
            Text(
              l10n.anonQuotaEmergencyNote,
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyMedium,
            ),
            const SizedBox(height: 12),
            // Always enabled: the native dialer over the SIM, without the API or an account.
            FilledButton.icon(
              key: const Key('anon-quota-call-198'),
              style: FilledButton.styleFrom(
                backgroundColor: theme.colorScheme.error,
                foregroundColor: theme.colorScheme.onError,
                minimumSize: const Size.fromHeight(56),
              ),
              onPressed: () async {
                final ok = await ref.read(dialerProvider)(civil.telUri);
                if (!ok && context.mounted) {
                  ScaffoldMessenger.of(context)
                      .showSnackBar(SnackBar(content: Text(l10n.dialFailed)));
                }
              },
              icon: const Icon(Icons.call),
              label: Text(l10n.callNumber(civil.number)),
            ),
            const SizedBox(height: 16),
            Text(l10n.anonQuotaExplanation, style: theme.textTheme.bodyLarge),
            const SizedBox(height: 24),
            FilledButton.icon(
              key: const Key('anon-quota-register'),
              onPressed: () => _signIn(context, ref, register: true),
              icon: const Icon(Icons.person_add),
              label: Text(l10n.citizenRegister),
            ),
            const SizedBox(height: 8),
            OutlinedButton(
              key: const Key('anon-quota-login'),
              onPressed: () => _signIn(context, ref, register: false),
              child: Text(l10n.citizenLogin),
            ),
            const SizedBox(height: 16),
            TextButton(
              onPressed: () => context.go(Routes.home),
              child: Text(l10n.reportBackHome),
            ),
          ],
        ),
      ),
    );
  }
}
