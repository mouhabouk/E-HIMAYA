import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/ui/components.dart';
import '../../core/ui/tokens.dart';
import '../../features/institution/org_text.dart';
import '../../l10n/app_localizations.dart';
import '../screens/field_widgets.dart';
import '../staff_chrome.dart';
import 'decision_screen.dart';
import 'grid_screen.dart';
import 'prevention_controller.dart';
import 'prevention_labels.dart';
import 'prevention_models.dart';
import 'sign_screen.dart';
import 'visits_screen.dart';

/// Opens [VisitScreen]; the steps come back to it with [backToVisit].
void openVisit(BuildContext context, String visitId) => unawaited(
  Navigator.of(context).push(
    MaterialPageRoute<void>(
      settings: const RouteSettings(name: VisitScreen.route),
      builder: (_) => VisitScreen(visitId: visitId),
    ),
  ),
);

bool backToVisit(Route<dynamic> r) =>
    r.settings.name == VisitScreen.route || r.isFirst;

/// One visit: take it, then the three steps on site, the grid, the signatures and the decision
/// (design §8.2 to §8.5).
class VisitScreen extends ConsumerWidget {
  const VisitScreen({super.key, required this.visitId});

  static const route = '/prevention/visit';

  final String visitId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final s = ref.watch(preventionControllerProvider);
    final v = s.visit(visitId);
    if (v == null) {
      return Scaffold(
        appBar: StaffAppBar(title: l10n.prevVisitsTitle),
        body: Center(child: Text(l10n.staffMissionGone)),
      );
    }
    final pack = s.packs[visitId];
    final n = Neutrals.of(context);
    final date = v.scheduledOn;
    return Scaffold(
      appBar: StaffAppBar(
        title: v.orgName,
        subtitle: orgKindText(l10n, v.orgKind),
      ),
      body: Column(
        children: [
          const ConnectionStrip(),
          const PendingBar(),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                AppCard(
                  key: const Key('visit-card'),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          const IconTile(Icons.apartment, tone: Tone.navy),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              v.orgName,
                              style: Theme.of(context).textTheme.titleLarge,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      if (v.orgAddress != null)
                        _Line(Icons.place, v.orgAddress!),
                      _Line(
                        Icons.event,
                        date == null
                            ? l10n.prevNoDate
                            : l10n.prevScheduledOn(visitDay(context, date)),
                      ),
                      if (v.inspectorName != null)
                        _Line(
                          Icons.badge,
                          l10n.orgVisitInspector(v.inspectorName!),
                        ),
                      const SizedBox(height: 6),
                      Pill(
                        visitStatusText(l10n, v.status),
                        tone: v.inspected ? Tone.amber : Tone.sky,
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
                if (pack == null) ...[
                  if (v.takenByOther)
                    AppCard(
                      key: const Key('visit-taken'),
                      color: Tone.slate.colors(context).tint,
                      child: Text(l10n.prevErrTaken),
                    )
                  else ...[
                    Text(l10n.prevTakeHelp, style: TextStyle(color: n.muted)),
                    const SizedBox(height: 12),
                    BigStepButton(
                      key: const Key('take-visit'),
                      label: l10n.prevTake,
                      icon: Icons.download_for_offline,
                      tone: Tone.navy,
                      onPressed: s.busy
                          ? null
                          : () => unawaited(
                              ref
                                  .read(preventionControllerProvider.notifier)
                                  .take(visitId),
                            ),
                    ),
                  ],
                  if (s.error != null) _Error(s.error!),
                ] else
                  ..._steps(context, pack),
              ],
            ),
          ),
        ],
      ),
    );
  }

  List<Widget> _steps(BuildContext context, VisitPack pack) {
    final l10n = AppLocalizations.of(context);
    final v = pack.visit;
    final d = pack.draft;
    final summary = GridSummary.of(v.checklist, d);
    final gridOpen = v.scheduled || d.signedOff;
    final decisionOpen = d.signedOff || v.inspected;
    return [
      if (gridOpen)
        NavCard(
          key: const Key('open-grid'),
          icon: Icons.checklist,
          tone: d.signedOff ? Tone.green : Tone.navy,
          title: d.signedOff || summary.notChecked < v.checklist.length
              ? l10n.prevContinueGrid
              : l10n.prevStartGrid,
          subtitle: [
            l10n.prevSummary(
              summary.conform,
              summary.nonconform,
              summary.notChecked,
            ),
            l10n.prevPhotos(d.photos.length),
          ].join(' · '),
          onTap: () => push(context, GridScreen(visitId: v.id)),
        ),
      if (gridOpen)
        NavCard(
          key: const Key('open-sign'),
          icon: Icons.draw,
          tone: d.signedOff ? Tone.green : Tone.navy,
          title: l10n.prevSignTitle,
          subtitle: d.signedOff
              ? (d.inspectionSent
                    ? l10n.prevInspectionSent
                    : l10n.prevInspectionQueued)
              : l10n.prevSuggested(visitDecisionText(l10n, summary.suggested)),
          onTap: () => push(context, SignScreen(visitId: v.id)),
        ),
      NavCard(
        key: const Key('open-decision'),
        icon: Icons.gavel,
        tone: decisionOpen ? Tone.amber : Tone.slate,
        title: l10n.prevDecisionTitle,
        subtitle: d.decision != null
            ? l10n.prevDecisionQueued
            : decisionOpen
            ? null
            : l10n.prevDecisionAfterInspection,
        onTap: decisionOpen
            ? () => push(context, DecisionScreen(visitId: v.id))
            : null,
      ),
      if (d.error != null) _Error(d.error!),
    ];
  }
}

class _Line extends StatelessWidget {
  const _Line(this.icon, this.text);

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    final n = Neutrals.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 18, color: n.muted),
          const SizedBox(width: 8),
          Expanded(child: Text(text)),
        ],
      ),
    );
  }
}

class _Error extends StatelessWidget {
  const _Error(this.code);

  final String code;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: 8),
    child: Text(
      visitErrorLabel(AppLocalizations.of(context), code),
      key: const Key('visit-error'),
      style: TextStyle(
        color: Theme.of(context).colorScheme.error,
        fontWeight: FontWeight.w600,
      ),
    ),
  );
}
