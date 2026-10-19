import 'package:flutter/material.dart';

import '../../core/db/app_database.dart';
import '../../core/http/models.dart';
import '../../l10n/app_localizations.dart';

String reportStatusLabel(AppLocalizations l10n, ReportStatus status) =>
    switch (status) {
      ReportStatus.received => l10n.statusReceived,
      ReportStatus.inProgress => l10n.statusInProgress,
      ReportStatus.intervened => l10n.statusIntervened,
      ReportStatus.ongoing => l10n.statusOngoing,
      ReportStatus.closed => l10n.statusClosed,
      ReportStatus.rejected => l10n.statusRejected,
    };

/// Label of the local sync state when the server status is not known (yet).
String localStateLabel(AppLocalizations l10n, String state) => switch (state) {
  ReportState.conflict => l10n.reportConflict,
  ReportState.failed => l10n.reportFailed,
  ReportState.blocked => l10n.reportBlocked,
  ReportState.orgRefused => l10n.reportOrgRefused,
  _ => l10n.reportPendingSync,
};

class ReportStatusChip extends StatelessWidget {
  const ReportStatusChip({super.key, required this.status});

  final ReportStatus status;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final scheme = Theme.of(context).colorScheme;
    final (bg, fg, icon) = switch (status) {
      ReportStatus.received => (
        scheme.secondaryContainer,
        scheme.onSecondaryContainer,
        Icons.inbox,
      ),
      ReportStatus.inProgress => (
        scheme.tertiaryContainer,
        scheme.onTertiaryContainer,
        Icons.hourglass_top,
      ),
      ReportStatus.intervened || ReportStatus.ongoing => (
        scheme.primaryContainer,
        scheme.onPrimaryContainer,
        Icons.local_fire_department,
      ),
      ReportStatus.closed => (
        scheme.surfaceContainerHighest,
        scheme.onSurface,
        Icons.check_circle,
      ),
      ReportStatus.rejected => (
        scheme.errorContainer,
        scheme.onErrorContainer,
        Icons.cancel,
      ),
    };
    return Chip(
      avatar: Icon(icon, size: 18, color: fg),
      label: Text(reportStatusLabel(l10n, status)),
      labelStyle: TextStyle(color: fg),
      backgroundColor: bg,
      side: BorderSide.none,
    );
  }
}

class LocalStateChip extends StatelessWidget {
  const LocalStateChip({super.key, required this.state});

  final String state;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final scheme = Theme.of(context).colorScheme;
    final problem =
        state == ReportState.failed ||
        state == ReportState.blocked ||
        state == ReportState.conflict ||
        state == ReportState.orgRefused;
    return Chip(
      avatar: Icon(
        problem ? Icons.error_outline : Icons.cloud_upload_outlined,
        size: 18,
      ),
      label: Text(localStateLabel(l10n, state)),
      backgroundColor: problem ? scheme.errorContainer : null,
      side: BorderSide.none,
    );
  }
}
