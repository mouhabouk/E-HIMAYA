import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart' show ScrollCacheExtent;
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/http/models.dart';
import '../../core/settings/settings_controller.dart';
import '../../core/ui/components.dart';
import '../../core/ui/tokens.dart';
import '../../features/report/category_labels.dart';
import '../../l10n/app_localizations.dart';
import '../staff_app.dart';
import '../staff_chrome.dart';
import '../staff_config.dart';
import '../staff_controller.dart';
import '../staff_labels.dart';
import '../staff_models.dart';
import 'detailed_report_screen.dart';
import 'field_flow.dart';
import 'field_widgets.dart';
import 'record_screen.dart';
import 'situation_screen.dart';
import 'staff_live_screen.dart';
import 'transport_screen.dart';

/// One mission (phase P4b, design §5.3): the card, the path of the five steps, one big button for
/// the next step, quick buttons, and "backup" and "danger" always at hand.
class MissionScreen extends ConsumerWidget {
  const MissionScreen({super.key, required this.missionId});

  final String missionId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final s = ref.watch(staffControllerProvider);
    final m = s.mission(missionId);
    if (m == null) {
      return Scaffold(
        appBar: StaffAppBar(title: l10n.staffMission),
        body: Center(child: Text(l10n.staffMissionGone)),
      );
    }
    final code = ref.watch(localeCodeProvider);
    final vehicle = s.me?.shift?.vehicle.label;
    final place = placeOf(m, code);
    final here = ref.watch(staffPositionProvider).value;
    final away = here == null || m.location == null
        ? null
        : distanceM(here, m.location!).round();
    final onScene =
        m.status == MissionStatus.onScene || m.status == MissionStatus.released;
    // Phase F: only the leader's phone records the mission; the crew reads it.
    final readOnly = s.me?.readOnly ?? false;
    return Scaffold(
      appBar: StaffAppBar(
        title: l10n.staffMission,
        subtitle: [?vehicle, place].where((x) => x.isNotEmpty).join(' · '),
      ),
      body: Column(
        children: [
          const ConnectionStrip(),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(16),
              // A handful of cards: all built, so the ones below the round button stay reachable.
              scrollCacheExtent: const ScrollCacheExtent.pixels(4000),
              children: [
                _MissionCard(mission: m, away: away),
                const SizedBox(height: 12),
                for (final a in m.alerts) AlertLine(alert: a),
                _Timeline(mission: m, away: away),
                const SizedBox(height: 12),
                if (readOnly)
                  const ReadOnlyBanner()
                else
                  _NextStep(mission: m, away: away),
                const StaffErrorText(),
                const SizedBox(height: 12),
                _QuickActions(mission: m),
                const SizedBox(height: 12),
                NatureChips(mission: m, readOnly: readOnly),
                const SizedBox(height: 12),
                MissionPointCard(mission: m),
                const SizedBox(height: 12),
                if (!readOnly && (m.over || m.leftSceneAt != null))
                  NavCard(
                    key: const Key('open-toll'),
                    icon: Icons.summarize,
                    tone: m.toll == null ? Tone.orange : Tone.green,
                    title: l10n.staffToll,
                    subtitle: m.toll == null
                        ? l10n.staffTollDue
                        : l10n.staffSentAt(
                            hhmm(m.toll!.createdAt ?? m.createdAt),
                          ),
                    onTap: () => push(context, TollScreen(missionId: m.id)),
                  ),
                if (!readOnly)
                  NavCard(
                    key: const Key('open-report'),
                    icon: Icons.record_voice_over,
                    tone: Tone.navy,
                    title: l10n.staffInterventionReport,
                    subtitle: m.interventionReport == null
                        ? l10n.staffInterventionReportDue
                        : l10n.staffSentAt(
                            hhmm(
                              m.interventionReport!.createdAt ?? m.createdAt,
                            ),
                          ),
                    onTap: () => push(
                      context,
                      InterventionReportScreen(missionId: m.id),
                    ),
                  ),
                // Phase D, review point 17: the room sees the scene live.
                if (!readOnly && !m.over)
                  NavCard(
                    key: const Key('open-live'),
                    icon: Icons.videocam,
                    tone: Tone.red,
                    title: l10n.staffLive,
                    subtitle: l10n.staffLiveSub,
                    onTap: () =>
                        push(context, StaffLiveScreen(missionId: m.id)),
                  ),
                if (onScene && !readOnly) ...[
                  const SizedBox(height: 12),
                  NavCard(
                    key: const Key('open-situation'),
                    icon: Icons.assignment,
                    tone: m.fieldReport == null ? Tone.orange : Tone.navy,
                    title: l10n.staffSituation,
                    subtitle: m.fieldReport == null
                        ? l10n.staffSituationDue
                        : l10n.staffSituationLast(
                            hhmm(m.fieldReport!.createdAt ?? m.createdAt),
                            severityLabel(l10n, m.fieldReport!.severity ?? 1),
                          ),
                    onTap: () =>
                        push(context, SituationScreen(missionId: m.id)),
                  ),
                  NavCard(
                    key: const Key('open-record'),
                    icon: Icons.groups,
                    tone: Tone.navy,
                    title: l10n.staffRecordTitle,
                    subtitle: l10n.staffRecordAgents(
                      m.crewCount ?? s.me?.shift?.crewSize ?? 0,
                    ),
                    onTap: () =>
                        push(context, MissionRecordScreen(missionId: m.id)),
                  ),
                  NavCard(
                    key: const Key('open-transports'),
                    icon: Icons.local_hospital,
                    tone: Tone.green,
                    title: l10n.staffTransportTitle,
                    subtitle: l10n.staffTransportsCount(m.transports.length),
                    onTap: () =>
                        push(context, TransportScreen(missionId: m.id)),
                  ),
                  if (m.template != null)
                    NavCard(
                      key: const Key('open-detailed'),
                      icon: Icons.fact_check,
                      tone: m.detailedReport == null ? Tone.purple : Tone.green,
                      title: l10n.staffDetailedReport,
                      subtitle: m.detailedReport == null
                          ? l10n.staffDetailedDue
                          : l10n.staffDetailedSent(
                              hhmm(m.detailedReport!.createdAt ?? m.createdAt),
                              m.detailedReport!.templateVersion ?? 1,
                            ),
                      onTap: () =>
                          push(context, DetailedReportScreen(missionId: m.id)),
                    ),
                ],
              ],
            ),
          ),
        ],
      ),
      bottomNavigationBar: m.active && !readOnly
          ? BottomActionBar(
              actions: [
                BarAction(
                  key: const Key('alert-backup'),
                  label: l10n.staffAskBackup,
                  icon: Icons.add_alert,
                  tone: Tone.red,
                  onPressed: () =>
                      unawaited(showCrewAlertSheet(context, m.id, 'backup')),
                ),
                BarAction(
                  key: const Key('alert-danger'),
                  label: l10n.staffCrewDanger,
                  icon: Icons.warning_amber,
                  tone: Tone.slate,
                  onPressed: () =>
                      unawaited(showCrewAlertSheet(context, m.id, 'danger')),
                ),
              ],
            )
          : null,
    );
  }
}

/// The mission card: red border, type, priority, place and distance, the room's note.
class _MissionCard extends ConsumerWidget {
  const _MissionCard({required this.mission, required this.away});

  final Mission mission;
  final int? away;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final m = mission;
    final n = Neutrals.of(context);
    final cat = m.category ?? ReportCategory.other;
    final place = placeOf(m, ref.watch(localeCodeProvider));
    final red = Tone.red.colors(context);
    return AppCard(
      key: const Key('mission-card'),
      borderColor: m.highPriority ? red.fill : null,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              IconTile(categoryIcon(cat), tone: Tone.red),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      m.title ?? categoryLabel(l10n, cat),
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    Text(
                      [
                        categoryLabel(l10n, cat),
                        missionStatusLabel(l10n, m.status),
                      ].join(' · '),
                      style: TextStyle(color: n.muted),
                    ),
                  ],
                ),
              ),
            ],
          ),
          if (m.highPriority) ...[
            const SizedBox(height: 8),
            Align(
              alignment: AlignmentDirectional.centerStart,
              child: Pill(
                l10n.staffHighPriority,
                tone: Tone.red,
                icon: Icons.bolt,
              ),
            ),
          ],
          if (place.isNotEmpty || away != null) ...[
            const SizedBox(height: 10),
            Row(
              children: [
                Icon(Icons.place, size: 18, color: n.muted),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    [
                      place,
                      if (away != null)
                        l10n.staffDistanceKm((away! / 1000).toStringAsFixed(1)),
                    ].where((x) => x.isNotEmpty).join(' · '),
                  ),
                ),
              ],
            ),
          ],
          if (m.order != null) ...[
            const SizedBox(height: 10),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Tone.amber.colors(context).tint,
                borderRadius: BorderRadius.circular(Radii.tile),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    l10n.staffRoomNote,
                    style: TextStyle(
                      color: Tone.amber.colors(context).onTint,
                      fontWeight: FontWeight.w700,
                      fontSize: 13,
                    ),
                  ),
                  Text(m.order!),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// The stations of the mission and the time of each (design §5.3), from the order to the return
/// to the unit (phase S2).
class _Timeline extends StatelessWidget {
  const _Timeline({required this.mission, required this.away});

  final Mission mission;
  final int? away;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final m = mission;
    final cancelled = m.status == MissionStatus.cancelled;
    // (label, time, done, current)
    final steps = <(String, DateTime?, bool, bool)>[
      (
        l10n.staffStepReceived,
        m.acknowledgedAt,
        m.acknowledgedAt != null,
        m.status == MissionStatus.ordered,
      ),
      (l10n.staffStepLeft, m.enRouteAt, m.enRouteAt != null, false),
      (
        m.status == MissionStatus.enRoute && away != null
            ? '${l10n.staffStepOnTheWay} · ${l10n.staffDistanceKm((away! / 1000).toStringAsFixed(1))}'
            : l10n.staffStepOnTheWay,
        null,
        m.onSceneAt != null,
        m.status == MissionStatus.enRoute,
      ),
      (
        l10n.staffStepArrived,
        m.onSceneAt,
        m.onSceneAt != null,
        m.status == MissionStatus.onScene,
      ),
      // Phase S2: after the arrival, leaving the scene, the hospital and the return to the unit.
      (
        l10n.staffStepLeftScene,
        m.leftSceneAt,
        m.leftSceneAt != null,
        m.status == MissionStatus.onScene && m.leftSceneAt == null,
      ),
      if (m.atHospitalAt != null || m.transports.isNotEmpty)
        (
          l10n.staffStepAtHospital,
          m.atHospitalAt,
          m.atHospitalAt != null,
          false,
        ),
      if (m.availableAt != null)
        (l10n.staffStepAvailable, m.availableAt, true, false),
      if (m.releasedAt != null &&
          m.backAtUnitAt == null &&
          m.availableAt == null)
        (l10n.staffStepOver, m.releasedAt, true, false),
      (l10n.staffStepBackAtUnit, m.backAtUnitAt, m.backAtUnitAt != null, false),
    ];
    final n = Neutrals.of(context);
    return AppCard(
      key: const Key('mission-timeline'),
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
      child: Column(
        children: [
          for (final (i, (label, at, done, current)) in steps.indexed)
            IntrinsicHeight(
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  SizedBox(
                    width: 26,
                    child: Column(
                      children: [
                        _Dot(done: done, current: current && !cancelled),
                        if (i < steps.length - 1)
                          Expanded(
                            child: Container(
                              width: 2,
                              color: done
                                  ? Tone.green.colors(context).fill
                                  : n.line,
                            ),
                          ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Padding(
                      padding: const EdgeInsets.only(bottom: 14, top: 1),
                      child: Text(
                        label,
                        style: TextStyle(
                          fontWeight: current || done
                              ? FontWeight.w700
                              : FontWeight.w500,
                          color: done || current ? n.ink : n.muted,
                        ),
                      ),
                    ),
                  ),
                  if (at != null)
                    Text(hhmm(at), style: TextStyle(color: n.muted)),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _Dot extends StatelessWidget {
  const _Dot({required this.done, required this.current});

  final bool done;
  final bool current;

  @override
  Widget build(BuildContext context) {
    final n = Neutrals.of(context);
    final green = Tone.green.colors(context).fill;
    final orange = Tone.orange.colors(context).fill;
    return Container(
      width: 22,
      height: 22,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: done ? green : (current ? orange : n.card),
        border: Border.all(
          color: done ? green : (current ? orange : n.line),
          width: 2,
        ),
      ),
      child: done
          ? const Icon(Icons.check, size: 14, color: Colors.white)
          : null,
    );
  }
}

/// The round button of the next step (phase F) with «تجاوز المرحلة» and «بدون تدخل»; arriving is
/// suggested within 150 m (F-STF-03).
class _NextStep extends StatelessWidget {
  const _NextStep({required this.mission, required this.away});

  final Mission mission;
  final int? away;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final m = mission;
    final near =
        m.status == MissionStatus.enRoute &&
        away != null &&
        away! <= StaffConfig.onSceneRadiusM;
    final caption = m.status == MissionStatus.enRoute && away != null && !near
        ? l10n.staffAwayFrom(away!)
        : m.nextStep == 'back_at_unit'
        ? l10n.staffBackEndsMission
        : null;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        MissionFlowPanel(mission: m, caption: caption),
        if (near)
          Semantics(
            liveRegion: true,
            child: Padding(
              key: const Key('on-scene-hint'),
              padding: const EdgeInsets.only(top: 6),
              child: Text(
                l10n.staffNearScene(away!),
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: Tone.orange.colors(context).onTint,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ),
      ],
    );
  }
}

/// Route, room, and the reporter when the room gave a number (design §5.3).
class _QuickActions extends ConsumerWidget {
  const _QuickActions({required this.mission});

  final Mission mission;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final launch = ref.read(staffLauncherProvider);
    final room = ref.read(staffConfigProvider).roomPhone;
    final loc = mission.destination;
    final contact = mission.contactPhone;
    Widget quick(String key, IconData icon, String label, Uri uri) => Expanded(
      child: OutlinedButton(
        key: Key(key),
        style: OutlinedButton.styleFrom(
          minimumSize: const Size(0, 64),
          padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 8),
        ),
        onPressed: () => unawaited(launch(uri)),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon),
            const SizedBox(height: 2),
            Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
    return Row(
      children: [
        if (loc != null)
          quick(
            'quick-route',
            Icons.navigation,
            l10n.staffRoute,
            Uri.parse(
              'https://www.google.com/maps/dir/?api=1&destination=${loc.lat},${loc.lon}',
            ),
          ),
        if (loc != null) const SizedBox(width: 8),
        quick('quick-room', Icons.call, l10n.staffRoom, Uri.parse('tel:$room')),
        if (contact != null) ...[
          const SizedBox(width: 8),
          quick(
            'quick-reporter',
            Icons.person,
            l10n.staffReporter,
            Uri.parse('tel:$contact'),
          ),
        ],
      ],
    );
  }
}
