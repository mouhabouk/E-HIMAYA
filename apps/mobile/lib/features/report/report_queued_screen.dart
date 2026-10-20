import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/db/app_database.dart';
import '../../core/http/api_error.dart';
import '../../core/http/models.dart';
import '../../core/routing/app_router.dart';
import '../../core/sync/report_queue.dart';
import '../../core/ui/theme.dart';
import '../../l10n/app_localizations.dart';
import '../emergency/dialer.dart';
import '../emergency/emergency_numbers.dart';
import '../institution/institution_providers.dart';
import '../institution/org_labels.dart';
import '../reports/reports_providers.dart';

/// Shown right after submit: the temporary code is available instantly, offline. It switches to
/// the server tracking code as soon as the sync engine gets it.
/// A stream can be opened while the report is queued (it is sent first) or on the server and
/// not closed.
bool _canGoLive(PendingReport row) {
  if (!ReportState.pendingStates.contains(row.state) &&
      row.state != ReportState.synced) {
    return false;
  }
  final status = ReportStatus.fromWire(row.serverStatus);
  return status != ReportStatus.closed && status != ReportStatus.rejected;
}

class ReportQueuedScreen extends ConsumerWidget {
  const ReportQueuedScreen({
    super.key,
    required this.tempCode,
    this.sos = false,
  });

  final String tempCode;
  final bool sos;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final local =
        ref.watch(localReportsProvider).value ?? const <PendingReport>[];
    final row = local.where((r) => r.tempCode == tempCode).firstOrNull;
    final serverCode = row?.serverTrackingCode;
    final code = serverCode ?? tempCode;
    final orgId = row == null ? null : payloadOrganizationId(row.payload);
    final civil = emergencyNumbers.first;
    return Scaffold(
      appBar: AppBar(
        title: Text(sos ? l10n.sosQueuedTitle : l10n.reportQueuedTitle),
        automaticallyImplyLeading: false,
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            Icon(
              serverCode == null ? Icons.cloud_queue : Icons.cloud_done,
              size: 64,
              color: theme.colorScheme.primary,
            ),
            const SizedBox(height: 16),
            Text(
              serverCode == null
                  ? l10n.reportTempCodeLabel
                  : l10n.trackingCodeLabel,
              textAlign: TextAlign.center,
              style: theme.textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            SelectableText(
              code,
              key: const Key('queued-code'),
              textAlign: TextAlign.center,
              textDirection: TextDirection.ltr,
              style: theme.textTheme.headlineMedium?.copyWith(
                fontWeight: FontWeight.w700,
              ),
            ),
            Center(
              child: TextButton.icon(
                onPressed: () async {
                  await Clipboard.setData(ClipboardData(text: code));
                  if (context.mounted) {
                    ScaffoldMessenger.of(context)
                        .showSnackBar(SnackBar(content: Text(l10n.copied)));
                  }
                },
                icon: const Icon(Icons.copy),
                label: Text(l10n.copyTrackingCode),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              serverCode == null
                  ? l10n.reportQueuedBody
                  : l10n.reportReceivedBody,
              textAlign: TextAlign.center,
            ),
            if (orgId != null) ...[
              const SizedBox(height: 8),
              Center(
                child: OrgChip(
                  key: const Key('queued-org'),
                  name: ref.watch(orgNamesProvider)[orgId] ?? '',
                ),
              ),
            ],
            if (row?.state == ReportState.orgRefused) ...[
              const SizedBox(height: 8),
              Text(
                row?.lastError == ApiErrorCode.orgNotActive.wire
                    ? l10n.reportOrgNotActiveBody
                    : l10n.reportOrgNotFoundBody,
                textAlign: TextAlign.center,
                style: TextStyle(color: theme.colorScheme.error),
              ),
            ],
            if (row?.state == ReportState.blocked) ...[
              const SizedBox(height: 8),
              Text(
                l10n.anonBlockedBody,
                textAlign: TextAlign.center,
                style: TextStyle(color: theme.colorScheme.error),
              ),
            ],
            if (sos) ...[
              const SizedBox(height: 24),
              FilledButton.icon(
                style: FilledButton.styleFrom(
                  backgroundColor: theme.colorScheme.error,
                  foregroundColor: theme.colorScheme.onError,
                ),
                onPressed: () => ref.read(dialerProvider)(civil.telUri),
                icon: const Icon(Icons.call),
                label: Text(l10n.callNumber(civil.number)),
              ),
            ],
            if (row != null && _canGoLive(row)) ...[
              const SizedBox(height: 16),
              // FR-A-031: go live on the report that was just created.
              OutlinedButton.icon(
                key: const Key('queued-go-live'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: sosRed,
                  side: const BorderSide(color: sosRed, width: 2),
                  minimumSize: const Size.fromHeight(56),
                ),
                onPressed: () => context.push(
                  Routes.liveFor(
                    clientUuid: row.clientUuid,
                    serverId: row.serverId,
                    trackingCode: code,
                    category: ReportCategory.fromWire(row.category),
                  ),
                ),
                icon: const Icon(Icons.videocam),
                label: Text(l10n.reportGoLive),
              ),
            ],
            const SizedBox(height: 24),
            OutlinedButton(
              onPressed: () => context.go(Routes.reports),
              child: Text(l10n.myReportsTitle),
            ),
            const SizedBox(height: 8),
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
