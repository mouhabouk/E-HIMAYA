import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart' show DateFormat, NumberFormat;

import '../../core/config/providers.dart';
import '../../core/http/error_messages.dart';
import '../../core/http/models.dart';
import '../../core/routing/app_router.dart';
import '../../core/ui/emergency_action.dart';
import '../../l10n/app_localizations.dart';
import '../emergency/dialer.dart';
import '../report/category_labels.dart';
import '../reports/status_chip.dart';
import 'institution_providers.dart';
import 'org_labels.dart';

/// Opens "My institution": the card directly when the account has a single institution,
/// otherwise the list.
void openMyInstitution(BuildContext context, List<MyOrg> orgs) {
  context.push(
    orgs.length == 1 ? Routes.institution(orgs.single.id) : Routes.institutions,
  );
}

/// The account's institutions (FR-A-081), all statuses, from the cached list when offline.
class MyInstitutionsScreen extends ConsumerWidget {
  const MyInstitutionsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final orgs = ref.watch(myOrgsProvider);
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.myInstitutionsTitle),
        actions: const [StandardAppBarActions()],
      ),
      body: RefreshIndicator(
        onRefresh: () => ref.read(myOrgsProvider.notifier).refresh(),
        child: orgs.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => _Message(text: errorMessageFor(l10n, e)),
          data: (items) => ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(16),
            children: [
              if (items.isEmpty) _Message(text: l10n.myInstitutionsEmpty),
              for (final org in items)
                Card(
                  child: ListTile(
                    key: Key('org-${org.id}'),
                    leading: const Icon(Icons.apartment, size: 32),
                    title: Text(org.name),
                    subtitle: Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Wrap(
                        spacing: 8,
                        runSpacing: 4,
                        crossAxisAlignment: WrapCrossAlignment.center,
                        children: [
                          Text(orgKindLabel(l10n, org.kind)),
                          OrgStatusChip(status: org.status),
                          if (org.alertsCount > 0)
                            Text(
                              l10n.orgAlertsCount(org.alertsCount),
                              style: TextStyle(color: theme.colorScheme.error),
                            ),
                        ],
                      ),
                    ),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => context.push(Routes.institution(org.id)),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

/// "My institution" (FR-A-081): short card from `GET /api/v1/orgs/{id}/summary` (offline copy
/// when the server cannot be reached) and the institution's recent reports. Detailed editing is
/// done on the institutions portal.
class MyInstitutionScreen extends ConsumerWidget {
  const MyInstitutionScreen({super.key, required this.orgId});

  final String orgId;

  Future<void> _refresh(WidgetRef ref) async {
    ref.invalidate(orgSummaryProvider(orgId));
    ref.invalidate(orgReportsProvider(orgId));
    try {
      await ref.read(orgSummaryProvider(orgId).future);
    } on Object {
      // Shown by the provider's error state.
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final summary = ref.watch(orgSummaryProvider(orgId));
    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.myInstitutionTitle),
        actions: const [StandardAppBarActions()],
      ),
      body: RefreshIndicator(
        onRefresh: () => _refresh(ref),
        child: summary.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(16),
            children: [_Message(text: errorMessageFor(l10n, e))],
          ),
          data: (view) => _SummaryBody(view: view),
        ),
      ),
    );
  }
}

class _SummaryBody extends ConsumerWidget {
  const _SummaryBody({required this.view});

  final OrgSummaryView view;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final locale = Localizations.localeOf(context).languageCode;
    final s = view.summary;
    final classification = s.classification;
    final offlineSince = view.offlineSince;
    return ListView(
      key: const Key('org-summary'),
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
      children: [
        if (offlineSince != null)
          Card(
            color: theme.colorScheme.tertiaryContainer,
            child: ListTile(
              leading: const Icon(Icons.cloud_off),
              title: Text(
                l10n.orgOfflineCopy(
                  DateFormat.yMMMd(locale)
                      .add_Hm()
                      .format(offlineSince.toLocal()),
                ),
              ),
            ),
          ),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(s.name, style: theme.textTheme.titleLarge),
                const SizedBox(height: 4),
                Wrap(
                  spacing: 8,
                  runSpacing: 4,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    Text(orgKindLabel(l10n, s.kind)),
                    OrgStatusChip(status: s.status),
                  ],
                ),
                const Divider(height: 24),
                if (s.capacity != null)
                  _InfoRow(
                    icon: Icons.groups,
                    label: l10n.orgCapacity,
                    value: NumberFormat.decimalPattern(locale)
                        .format(s.capacity!),
                  ),
                if (s.address != null && s.address!.isNotEmpty)
                  _InfoRow(
                    icon: Icons.place,
                    label: l10n.orgAddress,
                    value: s.address!,
                  ),
                if (classification != null)
                  _InfoRow(
                    icon: Icons.category,
                    label: l10n.orgClassification,
                    value: orgClassificationLabel(l10n, classification),
                    note: classification.provisional
                        ? l10n.orgClassificationProvisional
                        : null,
                  ),
                _InfoRow(
                  icon: s.alertsCount > 0
                      ? Icons.notification_important
                      : Icons.notifications_none,
                  label: l10n.orgAlerts,
                  value: s.alertsCount > 0
                      ? l10n.orgAlertsCount(s.alertsCount)
                      : l10n.orgNoAlerts,
                  highlight: s.alertsCount > 0,
                ),
              ],
            ),
          ),
        ),
        _Section(l10n.orgSafetyTeam),
        if (s.team.isEmpty) Text(l10n.orgTeamEmpty),
        for (final m in s.team) _TeamMemberTile(member: m),
        _Section(l10n.orgHazmatTitle(s.hazmatCount)),
        if (s.hazmat.isEmpty) Text(l10n.orgHazmatEmpty),
        for (final h in s.hazmat) _HazmatTile(item: h, locale: locale),
        const SizedBox(height: 16),
        const _PortalNote(),
        _Section(l10n.orgRecentReports),
        _OrgReports(orgId: s.id),
      ],
    );
  }
}

class _Section extends StatelessWidget {
  const _Section(this.text);
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsetsDirectional.only(top: 24, bottom: 8),
    child: Semantics(
      header: true,
      child: Text(text, style: Theme.of(context).textTheme.titleMedium),
    ),
  );
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({
    required this.icon,
    required this.label,
    required this.value,
    this.note,
    this.highlight = false,
  });

  final IconData icon;
  final String label;
  final String value;
  final String? note;
  final bool highlight;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color = highlight ? theme.colorScheme.error : null;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color ?? theme.colorScheme.onSurfaceVariant),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: theme.textTheme.bodySmall),
                Text(
                  value,
                  style: theme.textTheme.bodyLarge?.copyWith(color: color),
                ),
                if (note != null)
                  Text(
                    note!,
                    style: theme.textTheme.bodySmall?.copyWith(
                      fontStyle: FontStyle.italic,
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _TeamMemberTile extends ConsumerWidget {
  const _TeamMemberTile({required this.member});

  final OrgTeamMember member;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final phone = member.phone;
    final training = member.trainingStatus;
    final trainingProblem = training == 'expired' || training == 'unknown';
    return Card(
      child: ListTile(
        leading: Icon(
          member.teamRole == 'representative' ? Icons.shield : Icons.person,
        ),
        title: Text(member.fullName),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(teamRoleLabel(l10n, member.teamRole)),
            if (phone != null) Text(phone, textDirection: TextDirection.ltr),
            Text(
              l10n.orgTraining(trainingStatusLabel(l10n, training)),
              style: TextStyle(
                color: training == 'expiring'
                    ? theme.colorScheme.tertiary
                    : trainingProblem
                    ? theme.colorScheme.error
                    : null,
              ),
            ),
          ],
        ),
        isThreeLine: true,
        trailing: phone == null
            ? null
            : IconButton(
                key: Key('call-$phone'),
                tooltip: l10n.orgCallMember(member.fullName),
                icon: const Icon(Icons.call),
                onPressed: () =>
                    ref.read(dialerProvider)(Uri(scheme: 'tel', path: phone)),
              ),
      ),
    );
  }
}

class _HazmatTile extends StatelessWidget {
  const _HazmatTile({required this.item, required this.locale});

  final OrgHazmat item;
  final String locale;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final quantity = item.quantity;
    final details = [
      if (item.unNumber != null) l10n.orgUnNumber(item.unNumber!),
      if (quantity != null)
        '${NumberFormat.decimalPattern(locale).format(quantity)} '
            '${hazmatUnitSymbol(item.unit)}',
    ];
    return Card(
      child: ListTile(
        leading: const Icon(Icons.warning_amber),
        title: Text(item.name),
        subtitle: details.isEmpty ? null : Text(details.join(' · ')),
      ),
    );
  }
}

class _PortalNote extends ConsumerWidget {
  const _PortalNote();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final portal = ref.watch(appConfigProvider).portalUrl;
    return Card(
      color: theme.colorScheme.secondaryContainer,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              l10n.orgPortalNote,
              style: TextStyle(color: theme.colorScheme.onSecondaryContainer),
            ),
            const SizedBox(height: 4),
            Text(
              portal,
              textDirection: TextDirection.ltr,
              style: theme.textTheme.bodySmall,
            ),
            Align(
              alignment: AlignmentDirectional.centerEnd,
              child: TextButton.icon(
                key: const Key('open-portal'),
                onPressed: () async {
                  final messenger = ScaffoldMessenger.of(context);
                  final ok = await ref.read(urlOpenerProvider)(
                    Uri.parse(portal),
                  );
                  if (!ok) {
                    messenger.showSnackBar(
                      SnackBar(content: Text(l10n.orgPortalUnavailable)),
                    );
                  }
                },
                icon: const Icon(Icons.open_in_new),
                label: Text(l10n.orgOpenPortal),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _OrgReports extends ConsumerWidget {
  const _OrgReports({required this.orgId});

  final String orgId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final locale = Localizations.localeOf(context).languageCode;
    final fmt = DateFormat.yMMMd(locale).add_Hm();
    return ref
        .watch(orgReportsProvider(orgId))
        .when(
          loading: () => const LinearProgressIndicator(),
          error: (e, _) => Text(
            errorMessageFor(l10n, e),
            style: TextStyle(color: theme.colorScheme.error),
          ),
          data: (items) => Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (items.isEmpty) Text(l10n.orgReportsEmpty),
              for (final r in items) _OrgReportTile(report: r, format: fmt),
            ],
          ),
        );
  }
}

class _OrgReportTile extends StatelessWidget {
  const _OrgReportTile({required this.report, required this.format});

  final OrgReport report;
  final DateFormat format;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final category =
        ReportCategory.fromWire(report.category) ?? ReportCategory.other;
    final status = ReportStatus.fromWire(report.status);
    final received = report.receivedAt;
    final reporter = report.reporterDisplayName;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(categoryIcon(category)),
                const SizedBox(width: 8),
                Expanded(child: Text(categoryLabel(l10n, category))),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              report.trackingCode,
              textDirection: TextDirection.ltr,
              style: theme.textTheme.titleMedium,
            ),
            if (received != null)
              Text(
                format.format(received.toLocal()),
                style: theme.textTheme.bodySmall,
              ),
            if (reporter != null && reporter.isNotEmpty)
              Text(
                l10n.orgReportBy(reporter),
                style: theme.textTheme.bodySmall,
              ),
            const SizedBox(height: 4),
            status == null
                ? Text(l10n.statusUnknown)
                : ReportStatusChip(status: status),
          ],
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
