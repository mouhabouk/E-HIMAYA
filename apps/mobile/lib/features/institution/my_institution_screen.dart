import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart' show DateFormat, NumberFormat;

import '../../core/config/providers.dart';
import '../../core/http/error_messages.dart';
import '../../core/http/models.dart';
import '../../core/routing/app_router.dart';
import '../../core/ui/components.dart';
import '../../core/ui/emergency_action.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';
import '../emergency/dialer.dart';
import '../emergency/emergency_numbers.dart';
import '../report/category_labels.dart';
import '../reports/status_chip.dart';
import 'institution_providers.dart';
import 'kind_fields.dart';
import 'org_labels.dart';
import 'org_text.dart';

/// Opens "My institution": the card directly when the account has a single institution,
/// otherwise the list.
void openMyInstitution(BuildContext context, List<MyOrg> orgs) {
  context.push(
    orgs.length == 1 ? Routes.institution(orgs.single.id) : Routes.institutions,
  );
}

/// The account's institutions (FR-A-081), all statuses, from the cached list when offline, and
/// the way to register a new one (phase P2a).
class MyInstitutionsScreen extends ConsumerWidget {
  const MyInstitutionsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
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
              for (final org in items) ...[
                NavCard(
                  key: Key('org-${org.id}'),
                  icon: kindLook(org.kind).$1,
                  tone: kindLook(org.kind).$2,
                  title: org.name,
                  subtitle: [
                    orgKindLabel(l10n, org.kind),
                    orgStatusLabel(l10n, org.status),
                    if (org.alertsCount > 0)
                      l10n.orgAlertsCount(org.alertsCount),
                  ].join(' · '),
                  onTap: () => context.push(Routes.institution(org.id)),
                ),
                const SizedBox(height: 8),
              ],
              const SizedBox(height: 8),
              NavCard(
                key: const Key('org-register'),
                icon: Icons.add_business,
                tone: Tone.orange,
                title: l10n.orgRegister,
                onTap: () => context.push(Routes.institutionRegister),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// "My institution" (FR-A-081, redesigned in P2a): status, readiness ring, alerts, the sections
/// and the institution's recent reports, from `GET /api/v1/orgs/{id}/summary` (offline copy when
/// the server cannot be reached). Large files and full editing stay on the institutions portal.
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
      bottomNavigationBar: _InstitutionBar(
        orgId: orgId,
        active: summary.value?.summary.status == OrgStatus.active.wire,
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
    final locale = Localizations.localeOf(context).languageCode;
    final s = view.summary;
    final offlineSince = view.offlineSince;
    final (kindIcon, kindTone) = kindLook(s.kind);
    return ListView(
      key: const Key('org-summary'),
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
      children: [
        if (offlineSince != null)
          AppCard(
            color: Tone.amber.colors(context).tint,
            child: Row(
              children: [
                const Icon(Icons.cloud_off),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    l10n.orgOfflineCopy(
                      DateFormat.yMMMd(locale)
                          .add_Hm()
                          .format(offlineSince.toLocal()),
                    ),
                  ),
                ),
              ],
            ),
          ),
        const SizedBox(height: 8),
        AppCard(
          child: Row(
            children: [
              IconTile(kindIcon, tone: kindTone, size: 52),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(s.name, style: Theme.of(context).textTheme.titleLarge),
                    const SizedBox(height: 6),
                    Wrap(
                      spacing: 8,
                      runSpacing: 4,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        Text(orgKindLabel(l10n, s.kind)),
                        OrgStatusPill(status: s.status),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        if (s.status == OrgStatus.pendingReview.wire) ...[
          const SizedBox(height: 8),
          AppCard(
            color: Tone.amber.colors(context).tint,
            child: Text(l10n.orgPendingNote),
          ),
        ],
        const SizedBox(height: 8),
        _Readiness(summary: s),
        if (s.messagesPending > 0)
          NavCard(
            key: const Key('org-messages-pending'),
            icon: Icons.mark_email_unread,
            tone: Tone.red,
            title: l10n.orgMessagesPending(s.messagesPending),
            subtitle: l10n.orgMessagesPendingHint,
            trailing: Pill('${s.messagesPending}', tone: Tone.red),
            onTap: () => context.push(
              Routes.institutionSection(s.id, InstitutionSection.messages.name),
            ),
          ),
        SectionTitle(l10n.orgAlerts),
        if (s.alerts.isEmpty && s.alertsCount == 0) Text(l10n.orgNoAlerts),
        if (s.alerts.isEmpty && s.alertsCount > 0)
          Text(l10n.orgAlertsCount(s.alertsCount)),
        for (final a in s.alerts) ...[
          _AlertRow(alert: a, locale: locale),
          const SizedBox(height: 8),
        ],
        SectionTitle(l10n.orgSectionsTitle),
        _SectionsGrid(summary: s),
        const SizedBox(height: 16),
        SectionTitle(l10n.orgRecentReports),
        OrgReportsList(orgId: s.id),
      ],
    );
  }
}

/// Readiness ring (P2a): share of the safety requirements met, with what is still missing.
class _Readiness extends StatelessWidget {
  const _Readiness({required this.summary});

  final OrgSummary summary;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final readiness = summary.readiness;
    final missing = summary.missing;
    return AppCard(
      key: const Key('org-readiness'),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (readiness != null)
            ProgressRing(
              value: readiness / 100,
              tone: readiness == 100 ? Tone.green : Tone.orange,
            ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(l10n.orgReadiness, style: theme.textTheme.titleMedium),
                const SizedBox(height: 4),
                Text(
                  missing.isEmpty
                      ? l10n.orgReadinessDone
                      : l10n.orgReadinessMissing(missing.length),
                ),
                for (final m in missing)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Icon(
                          Icons.radio_button_unchecked,
                          size: 16,
                          color: Neutrals.of(context).muted,
                        ),
                        const SizedBox(width: 6),
                        Expanded(
                          child: Text(
                            requirementText(l10n, m),
                            style: theme.textTheme.bodySmall,
                          ),
                        ),
                      ],
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

class _AlertRow extends StatelessWidget {
  const _AlertRow({required this.alert, required this.locale});

  final OrgAlert alert;
  final String locale;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final overdue =
        alert.kind.endsWith('expired') || alert.kind.endsWith('overdue');
    final since = alert.since;
    return AppCard(
      child: Row(
        children: [
          IconTile(
            overdue ? Icons.error_outline : Icons.schedule,
            tone: overdue ? Tone.red : Tone.amber,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(orgAlertText(l10n, alert.kind)),
                if (since != null)
                  Text(
                    DateFormat.yMMMd(locale).format(since.toLocal()),
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// The sections of the institution (P2a): quick actions on the phone, the portal for the rest.
class _SectionsGrid extends ConsumerWidget {
  const _SectionsGrid({required this.summary});

  final OrgSummary summary;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final id = summary.id;
    void open(String section) =>
        context.push(Routes.institutionSection(id, section));
    final tiles = [
      (
        InstitutionSection.messages,
        Icons.mark_email_unread,
        Tone.red,
        l10n.orgSectionMessages,
      ),
      (InstitutionSection.card, Icons.badge, Tone.navy, l10n.orgSectionCard),
      (InstitutionSection.team, Icons.groups, Tone.green, l10n.orgSafetyTeam),
      (
        InstitutionSection.equipment,
        Icons.fire_extinguisher,
        Tone.red,
        l10n.orgSectionEquipment,
      ),
      (
        InstitutionSection.hazmat,
        Icons.warning_amber,
        Tone.amber,
        l10n.orgSectionHazmat,
      ),
      (
        InstitutionSection.evacuation,
        Icons.directions_run,
        Tone.teal,
        l10n.orgSectionEvacuation,
      ),
      (
        InstitutionSection.reports,
        Icons.campaign,
        Tone.orange,
        l10n.orgSectionReports,
      ),
      (
        InstitutionSection.certificates,
        Icons.verified,
        Tone.purple,
        l10n.orgSectionCertificates,
      ),
      (
        InstitutionSection.records,
        Icons.summarize,
        Tone.navy,
        l10n.orgSectionRecords,
      ),
      (
        InstitutionSection.activities,
        Icons.event_available,
        Tone.pink,
        l10n.orgSectionActivities,
      ),
      (
        InstitutionSection.awareness,
        Icons.lightbulb,
        Tone.green,
        l10n.orgSectionAwareness,
      ),
      (
        InstitutionSection.members,
        Icons.manage_accounts,
        Tone.sky,
        l10n.orgSectionMembers,
      ),
    ];
    return TileGrid(
      minTileWidth: 100,
      children: [
        for (final (section, icon, tone, title) in tiles)
          ChoiceTile(
            key: Key('org-section-${section.name}'),
            icon: icon,
            tone: tone,
            title: title,
            onTap: () => open(section.name),
          ),
        ChoiceTile(
          key: const Key('open-portal'),
          icon: Icons.open_in_new,
          tone: Tone.slate,
          title: l10n.orgSectionPortal,
          onTap: () => openPortal(context, ref),
        ),
      ],
    );
  }
}

/// Opens the institutions portal (large files, full editing), or says it cannot.
Future<void> openPortal(BuildContext context, WidgetRef ref) async {
  final l10n = AppLocalizations.of(context);
  final messenger = ScaffoldMessenger.of(context);
  final portal = ref.read(appConfigProvider).portalUrl;
  final ok = await ref.read(urlOpenerProvider)(Uri.parse(portal));
  if (!ok) {
    messenger.showSnackBar(SnackBar(content: Text(l10n.orgPortalUnavailable)));
  }
}

/// Sections opened from the institution's home (`/institutions/:id/:section`).
enum InstitutionSection {
  messages,
  card,
  team,
  equipment,
  hazmat,
  evacuation,
  reports,
  certificates,
  records,
  activities,
  awareness,
  members;

  static InstitutionSection? fromName(String? name) {
    for (final s in values) {
      if (s.name == name) return s;
    }
    return null;
  }
}

/// Bottom bar of the institution's home: 198 first, then reporting for the institution.
class _InstitutionBar extends ConsumerWidget {
  const _InstitutionBar({required this.orgId, required this.active});

  final String orgId;
  final bool active;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final civil = emergencyNumbers.first;
    return BottomActionBar(
      actions: [
        BarAction(
          key: const Key('org-call-198'),
          label: l10n.homeCall198,
          icon: Icons.phone_rounded,
          tone: Tone.red,
          onPressed: () => ref.read(dialerProvider)(civil.telUri),
        ),
        if (active)
          BarAction(
            key: const Key('org-report-as'),
            label: l10n.orgReportAs,
            icon: Icons.campaign,
            tone: Tone.navy,
            onPressed: () async {
              await ref.read(reportAsChoiceProvider.notifier).choose(orgId);
              if (context.mounted) await context.push(Routes.newReport);
            },
          ),
      ],
    );
  }
}

class TeamMemberTile extends ConsumerWidget {
  const TeamMemberTile({super.key, required this.member});

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

class HazmatTile extends StatelessWidget {
  const HazmatTile({super.key, required this.item, required this.locale});

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

class OrgReportsList extends ConsumerWidget {
  const OrgReportsList({super.key, required this.orgId});

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
