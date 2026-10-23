import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/db/app_database.dart';
import '../../core/db/open_database.dart';
import '../../core/routing/app_router.dart';
import '../../core/ui/emergency_action.dart';
import '../../l10n/app_localizations.dart';
import 'safety_providers.dart';
import 'safety_widgets.dart';

/// Addition 8.7: what this phone sent, kept on the phone only; and the alerts received from
/// linked contacts in the last 24 hours (from the server).
class SafetyRecentScreen extends ConsumerWidget {
  const SafetyRecentScreen({super.key});

  String _kind(AppLocalizations l10n, String kind) => switch (kind) {
    'sos_message' => l10n.safetyRecentSos,
    'safety_check' => l10n.safetyCheckTitle,
    'live_share' => l10n.safetyLiveTitle,
    _ => l10n.safetyTestTitle,
  };

  String _status(AppLocalizations l10n, String status) => switch (status) {
    'sent' => l10n.safetyRecentSent,
    'cancelled' => l10n.safetyRecentCancelled,
    'ok' => l10n.safetyRecentOk,
    _ => l10n.safetyRecentFailed,
  };

  String _channels(AppLocalizations l10n, SafetyAlertEntry e) => e.channels
      .split(',')
      .where((c) => c.isNotEmpty)
      .map(
        (c) => switch (c) {
          'app' => l10n.safetyChannelApp,
          'sms' => 'SMS',
          _ => 'WhatsApp',
        },
      )
      .join(' + ');

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final entries = ref.watch(safetyRecentProvider).value ?? const [];
    final received = (ref.watch(safetyAlertsProvider).value ?? const [])
        .where((a) => !a.mine)
        .toList();
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.safetyRecentTitle),
        actions: const [StandardAppBarActions()],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (received.isNotEmpty) ...[
              Text(
                l10n.safetyRecentReceived,
                style: theme.textTheme.titleMedium,
              ),
              for (final a in received)
                Card(
                  child: ListTile(
                    key: Key('received-${a.id}'),
                    leading: const Icon(Icons.sos, color: Colors.red),
                    title: Text(
                      a.isCheck
                          ? l10n.safetyAlertCheckFrom(
                              a.senderFirstName ?? l10n.safetySomeone,
                            )
                          : l10n.safetyAlertFrom(
                              a.senderFirstName ?? l10n.safetySomeone,
                            ),
                    ),
                    subtitle: Text(safetyTime(context, a.createdAt)),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => context.push(Routes.safetyAlert(a.id)),
                  ),
                ),
              const SizedBox(height: 16),
            ],
            Row(
              children: [
                Expanded(
                  child: Text(
                    l10n.safetyRecentSentTitle,
                    style: theme.textTheme.titleMedium,
                  ),
                ),
                if (entries.isNotEmpty)
                  TextButton(
                    key: const Key('recent-clear'),
                    onPressed: () =>
                        ref.read(databaseProvider).clearAlertHistory(),
                    child: Text(l10n.safetyRecentClear),
                  ),
              ],
            ),
            if (entries.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 24),
                child: Text(
                  l10n.safetyRecentEmpty,
                  textAlign: TextAlign.center,
                ),
              ),
            for (final e in entries)
              ListTile(
                key: Key('recent-${e.id}'),
                leading: Icon(switch (e.kind) {
                  'sos_message' => Icons.sms_failed,
                  'safety_check' => Icons.timer,
                  'live_share' => Icons.share_location,
                  _ => Icons.fact_check,
                }),
                title: Text(_kind(l10n, e.kind)),
                subtitle: Text(
                  [
                    safetyTime(context, e.at),
                    _status(l10n, e.status),
                    if (e.channels.isNotEmpty) _channels(l10n, e),
                    if (e.recipients > 0)
                      l10n.safetyRecentRecipients(e.recipients),
                  ].join(' · '),
                ),
              ),
            const SizedBox(height: 8),
            Text(l10n.safetyRecentPrivacy, style: theme.textTheme.bodySmall),
          ],
        ),
      ),
    );
  }
}
