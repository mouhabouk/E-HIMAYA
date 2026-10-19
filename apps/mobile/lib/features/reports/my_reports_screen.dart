import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart' show DateFormat;

import '../../core/http/error_messages.dart';
import '../../core/routing/app_router.dart';
import '../../core/sync/sync_scheduler.dart';
import '../../core/ui/emergency_action.dart';
import '../../l10n/app_localizations.dart';
import '../report/category_labels.dart';
import 'reports_providers.dart';
import 'status_chip.dart';

/// FR-A-032: local queue merged with the server list, pull-to-refresh, tracking-code copy.
class MyReportsScreen extends ConsumerWidget {
  const MyReportsScreen({super.key});

  Future<void> _refresh(WidgetRef ref) async {
    await ref.read(requestSyncProvider)();
    await ref.read(serverReportsProvider.notifier).refresh();
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final merged = ref.watch(mergedReportsProvider);
    final server = ref.watch(serverReportsProvider);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.myReportsTitle),
        actions: [
          IconButton(
            tooltip: l10n.trackTitle,
            icon: const Icon(Icons.manage_search),
            onPressed: () => context.push(Routes.track),
          ),
          const EmergencyNumbersAction(),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () => _refresh(ref),
        child: merged.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => _Message(text: errorMessageFor(l10n, e)),
          data: (items) => ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 96),
            children: [
              if (server.hasError)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Text(
                    '${l10n.myReportsOffline} ${errorMessageFor(l10n, server.error!)}',
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ),
              if (items.isEmpty) _Message(text: l10n.myReportsEmpty),
              for (final item in items) ReportTile(item: item),
            ],
          ),
        ),
      ),
    );
  }
}

class _Message extends StatelessWidget {
  const _Message({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 48),
    child: Text(text, textAlign: TextAlign.center),
  );
}

class ReportTile extends StatelessWidget {
  const ReportTile({super.key, required this.item});

  final ReportListItem item;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final locale = Localizations.localeOf(context).languageCode;
    final date = DateFormat.yMMMd(locale)
        .add_Hm()
        .format(item.createdAt.toLocal());
    final status = item.status;
    return Card(
      child: Padding(
        padding: const EdgeInsetsDirectional.fromSTEB(16, 12, 4, 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(categoryIcon(item.category)),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    categoryLabel(l10n, item.category),
                    style: theme.textTheme.titleMedium,
                  ),
                ),
                IconButton(
                  tooltip: l10n.copyTrackingCode,
                  icon: const Icon(Icons.copy),
                  onPressed: () async {
                    await Clipboard.setData(
                      ClipboardData(text: item.trackingCode),
                    );
                    if (context.mounted) {
                      ScaffoldMessenger.of(context)
                          .showSnackBar(SnackBar(content: Text(l10n.copied)));
                    }
                  },
                ),
              ],
            ),
            Text(
              item.trackingCode,
              textDirection: TextDirection.ltr,
              style: theme.textTheme.titleLarge?.copyWith(
                fontFeatures: const [FontFeature.tabularFigures()],
              ),
            ),
            if (item.isTemporary)
              Text(l10n.temporaryCodeNote, style: theme.textTheme.bodySmall),
            const SizedBox(height: 4),
            Text(date, style: theme.textTheme.bodySmall),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 4,
              children: [
                if (status != null) ReportStatusChip(status: status),
                if (status == null && item.localState != null)
                  LocalStateChip(state: item.localState!),
                if (item.mediaPending > 0)
                  Chip(
                    avatar: const Icon(Icons.attach_file, size: 18),
                    label: Text(l10n.reportUploadingMedia(item.mediaPending)),
                    side: BorderSide.none,
                  ),
                if (item.mediaFailed > 0)
                  Chip(
                    avatar: const Icon(Icons.error_outline, size: 18),
                    label: Text(l10n.reportMediaRejected(item.mediaFailed)),
                    backgroundColor: theme.colorScheme.errorContainer,
                    side: BorderSide.none,
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
