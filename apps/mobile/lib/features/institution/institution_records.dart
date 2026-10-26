import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart' show DateFormat;

import '../../core/config/providers.dart';
import '../../core/http/ehimaya_api.dart';
import '../../core/http/error_messages.dart';
import '../../core/http/models.dart';
import '../../core/settings/settings_controller.dart';
import '../../core/ui/components.dart';
import '../../core/ui/sim_banner.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';
import 'institution_providers.dart';
import 'org_text.dart';

/// "Reports and records" of the institution (phase P3b, F-APP-132,
/// docs/phase-p3/design-prevention.md §8): reminders, prevention visits with their report and
/// comparison, reservations and deadlines, certificates, and the annual report with the drills.
/// Read only: visit requests and answers to reservations stay on the portal.
class OrgRecordsSection extends ConsumerStatefulWidget {
  const OrgRecordsSection({super.key, required this.orgId});

  final String orgId;

  @override
  ConsumerState<OrgRecordsSection> createState() => _OrgRecordsSectionState();
}

class _OrgRecordsSectionState extends ConsumerState<OrgRecordsSection> {
  int? _year;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final orgId = widget.orgId;
    final thisYear = ref.watch(clockProvider)().year;
    final year = _year ?? thisYear;
    final visits = ref.watch(orgVisitsProvider(orgId));
    final open = [
      for (final v in visits.value ?? const <PreventionVisit>[])
        for (final r in v.reservations)
          if (r.state != 'lifted') r,
    ]..sort((a, b) => a.dueOn.compareTo(b.dueOn));
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(l10n.orgRecordsHint, style: Theme.of(context).textTheme.bodySmall),
        SectionTitle(l10n.orgRecordsReminders),
        _Reminders(orgId: orgId),
        SectionTitle(l10n.orgRecordsVisits),
        visits.when(
          loading: _loading,
          error: (e, _) => _Note(errorMessageFor(l10n, e), error: true),
          data: (items) => Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (items.isEmpty) _Note(l10n.orgRecordsVisitsEmpty),
              for (final v in items) _VisitCard(orgId: orgId, visit: v),
            ],
          ),
        ),
        SectionTitle(l10n.orgRecordsReservations),
        if (visits.hasValue && open.isEmpty)
          _Note(l10n.orgRecordsReservationsEmpty),
        for (final r in open) _ReservationTile(reservation: r),
        SectionTitle(l10n.orgSectionCertificates),
        _CertificateList(orgId: orgId),
        Row(
          children: [
            Expanded(child: SectionTitle(l10n.orgRecordsAnnual)),
            DropdownButton<int>(
              key: const Key('org-records-year'),
              value: year,
              underline: const SizedBox.shrink(),
              hint: Text(l10n.orgRecordsYear),
              items: [
                for (var y = thisYear; y >= thisYear - 4 && y >= 2020; y--)
                  DropdownMenuItem(value: y, child: Text('$y')),
              ],
              onChanged: (y) => setState(() => _year = y),
            ),
          ],
        ),
        _Annual(orgId: orgId, year: year),
      ],
    );
  }
}

class _Note extends StatelessWidget {
  const _Note(this.text, {this.error = false});

  final String text;
  final bool error;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 12),
    child: Text(
      text,
      style: error
          ? TextStyle(color: Theme.of(context).colorScheme.error)
          : null,
    ),
  );
}

Widget _loading() => const Padding(
  padding: EdgeInsets.all(24),
  child: Center(child: CircularProgressIndicator()),
);

/// Asks the API for a short-lived link, then opens it outside the app.
Future<void> _openPdf(
  BuildContext context,
  WidgetRef ref,
  Future<Uri> Function(EHimayaApi api) link,
) async {
  final l10n = AppLocalizations.of(context);
  final messenger = ScaffoldMessenger.of(context);
  var ok = false;
  try {
    ok = await ref.read(urlOpenerProvider)(await link(ref.read(apiProvider)));
  } on Exception {
    ok = false;
  }
  if (!ok) {
    messenger
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(l10n.orgPdfUnavailable)));
  }
}

Tone _decisionTone(String? decision) => switch (decision) {
  'approved' => Tone.green,
  'approved_with_reservations' => Tone.amber,
  'refused' => Tone.red,
  _ => Tone.slate,
};

Tone _stateTone(String state) => switch (state) {
  'lifted' => Tone.green,
  'overdue' => Tone.red,
  _ => Tone.amber,
};

class _Reminders extends ConsumerWidget {
  const _Reminders({required this.orgId});

  final String orgId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final alerts =
        ref.watch(orgSummaryProvider(orgId)).value?.summary.alerts ??
        const <OrgAlert>[];
    if (alerts.isEmpty) return _Note(l10n.orgRecordsRemindersEmpty);
    return Wrap(
      spacing: 8,
      runSpacing: 6,
      children: [
        for (final a in alerts)
          Pill(
            orgAlertText(l10n, a.kind),
            tone: a.kind.endsWith('overdue') || a.kind.endsWith('expired')
                ? Tone.red
                : Tone.amber,
            icon: Icons.notifications_active,
          ),
      ],
    );
  }
}

class _VisitCard extends ConsumerWidget {
  const _VisitCard({required this.orgId, required this.visit});

  final String orgId;
  final PreventionVisit visit;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final date = DateFormat.yMMMd(ref.watch(localeCodeProvider));
    final v = visit;
    final day = v.inspectedOn ?? v.scheduledOn;
    final certificate = v.certificate;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: AppCard(
        key: Key('org-visit-${v.id}'),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                IconTile(Icons.policy, tone: _decisionTone(v.decision)),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        visitOriginText(l10n, v.origin),
                        style: theme.textTheme.titleMedium,
                      ),
                      if (day != null) Text(l10n.orgVisitOn(date.format(day))),
                      if (v.inspectorName case final String name)
                        Text(
                          l10n.orgVisitInspector(name),
                          style: theme.textTheme.bodySmall,
                        ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 4,
              children: [
                Pill(visitStatusText(l10n, v.status), tone: Tone.slate),
                if (v.decision case final String d)
                  Pill(visitDecisionText(l10n, d), tone: _decisionTone(d)),
              ],
            ),
            if (v.comparison case final VisitComparison c) ...[
              const SizedBox(height: 6),
              Text(
                l10n.orgVisitComparison(c.conform, c.nonconform, c.notChecked),
                key: Key('org-visit-comparison-${v.id}'),
              ),
            ],
            if (v.decisionReason case final String reason)
              Text(l10n.orgVisitReason(reason)),
            if (certificate != null) ...[
              const SizedBox(height: 6),
              Text(certificate.code, textDirection: TextDirection.ltr),
              const _SimTag(),
            ],
            if (v.hasReport || certificate != null) const SizedBox(height: 6),
            Wrap(
              spacing: 8,
              children: [
                if (v.hasReport)
                  OutlinedButton.icon(
                    key: Key('org-visit-report-${v.id}'),
                    onPressed: () => _openPdf(
                      context,
                      ref,
                      (api) => api.visitReportUrl(orgId, v.id),
                    ),
                    icon: const Icon(Icons.picture_as_pdf),
                    label: Text(l10n.orgVisitReport),
                  ),
                if (certificate != null && certificate.id.isNotEmpty)
                  OutlinedButton.icon(
                    key: Key('org-visit-certificate-${v.id}'),
                    onPressed: () => _openPdf(
                      context,
                      ref,
                      (api) => api.certificatePdfUrl(orgId, certificate.id),
                    ),
                    icon: const Icon(Icons.verified),
                    label: Text(l10n.orgCertificatePdf),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// The prevention certificate's model and seal are not the Office's yet.
class _SimTag extends StatelessWidget {
  const _SimTag();

  @override
  Widget build(BuildContext context) => Container(
    margin: const EdgeInsets.only(top: 4),
    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
    decoration: BoxDecoration(
      color: simAmber,
      borderRadius: BorderRadius.circular(4),
    ),
    child: Text(
      AppLocalizations.of(context).orgCertPreventionSim,
      style: const TextStyle(color: Colors.black87, fontSize: 12),
    ),
  );
}

class _ReservationTile extends ConsumerWidget {
  const _ReservationTile({required this.reservation});

  final VisitReservation reservation;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final date = DateFormat.yMMMd(ref.watch(localeCodeProvider));
    final r = reservation;
    return NavCard(
      key: Key('org-reservation-${r.id}'),
      icon: r.state == 'overdue' ? Icons.error_outline : Icons.schedule,
      tone: _stateTone(r.state),
      title: r.text,
      subtitle: [
        reservationStateText(l10n, r.state),
        l10n.orgReservationDue(date.format(r.dueOn)),
      ].join(' · '),
    );
  }
}

class _CertificateList extends ConsumerWidget {
  const _CertificateList({required this.orgId});

  final String orgId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final date = DateFormat.yMMMd(ref.watch(localeCodeProvider));
    return ref
        .watch(orgCertificatesProvider(orgId))
        .when(
          loading: _loading,
          error: (e, _) => _Note(errorMessageFor(l10n, e), error: true),
          data: (items) => Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (items.isEmpty) _Note(l10n.orgCertificatesEmpty),
              for (final c in items)
                NavCard(
                  key: Key('org-record-cert-${c.code}'),
                  icon: c.kind == 'prevention' ? Icons.policy : Icons.verified,
                  tone: c.status == 'approved' ? Tone.green : Tone.slate,
                  title: '${certificateKindText(l10n, c.kind)} · ${c.code}',
                  subtitle: [
                    certificateStatusText(l10n, c.status),
                    if (c.validUntil case final DateTime until)
                      l10n.orgCertificateValidUntil(date.format(until)),
                  ].join(' · '),
                  trailing: c.status == 'approved' && c.id.isNotEmpty
                      ? IconButton(
                          key: Key('org-record-cert-pdf-${c.code}'),
                          tooltip: l10n.orgCertificatePdf,
                          icon: const Icon(Icons.picture_as_pdf),
                          onPressed: () => _openPdf(
                            context,
                            ref,
                            (api) => api.certificatePdfUrl(orgId, c.id),
                          ),
                        )
                      : null,
                ),
            ],
          ),
        );
  }
}

class _Annual extends ConsumerWidget {
  const _Annual({required this.orgId, required this.year});

  final String orgId;
  final int year;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final date = DateFormat.yMMMd(ref.watch(localeCodeProvider));
    return ref
        .watch(orgAnnualReportProvider((orgId, year)))
        .when(
          loading: _loading,
          error: (e, _) => _Note(errorMessageFor(l10n, e), error: true),
          data: (a) => Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              AppCard(
                key: const Key('org-annual'),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    for (final line in [
                      l10n.orgAnnualDrills(a.drills.length, a.participants),
                      l10n.orgAnnualEvents(a.events.length),
                      l10n.orgAnnualMaintenance(a.maintenance),
                      l10n.orgAnnualTraining(
                        a.training.valid,
                        a.training.expiring,
                        a.training.expired,
                      ),
                      l10n.orgAnnualVisits(a.visits.length),
                      l10n.orgAnnualReservations(
                        a.reservationsOpened,
                        a.reservationsLifted,
                        a.reservationsOverdue,
                      ),
                      l10n.orgAnnualCertificates(
                        a.certificates.length,
                        a.stamps,
                      ),
                      l10n.orgAnnualReports(a.reports),
                    ])
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 2),
                        child: Text(line),
                      ),
                  ],
                ),
              ),
              SectionTitle(l10n.orgRecordsDrills),
              if (a.drills.isEmpty) _Note(l10n.orgRecordsDrillsEmpty),
              for (final d in a.drills)
                NavCard(
                  key: Key('org-drill-${d.id}'),
                  icon: Icons.directions_run,
                  tone: Tone.orange,
                  title: d.title,
                  subtitle: [
                    date.format(d.startsOn),
                    if (d.participants case final int n)
                      l10n.orgActivityParticipantsCount(n),
                    if (d.notes case final String notes) notes,
                  ].join(' · '),
                ),
            ],
          ),
        );
  }
}
