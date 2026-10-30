import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/http/models.dart';
import '../../core/location/location_service.dart';
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
import 'field_widgets.dart';
import 'record_screen.dart';
import 'situation_screen.dart';
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
              children: [
                _MissionCard(mission: m, away: away),
                const SizedBox(height: 12),
                for (final a in m.alerts) AlertLine(alert: a),
                _Timeline(mission: m, away: away),
                const SizedBox(height: 12),
                _NextStep(mission: m, away: away, busy: s.busy),
                const StaffErrorText(),
                const SizedBox(height: 12),
                _QuickActions(mission: m),
                if (onScene) ...[
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
      bottomNavigationBar: m.active
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
      if (m.releasedAt != null && m.backAtUnitAt == null)
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

/// The big button of the next step; arriving is suggested within 150 m (F-STF-03).
class _NextStep extends ConsumerWidget {
  const _NextStep({
    required this.mission,
    required this.away,
    required this.busy,
  });

  final Mission mission;
  final int? away;
  final bool busy;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final m = mission;
    final (String status, String label, IconData icon, Tone tone)? next =
        switch (m.status) {
          MissionStatus.ordered => (
            'en_route',
            l10n.staffStepLeft,
            Icons.directions_car,
            Tone.orange,
          ),
          MissionStatus.enRoute => (
            'on_scene',
            l10n.staffStepArrived,
            Icons.place,
            Tone.orange,
          ),
          _ => null,
        };
    if (next == null) {
      return _Milestones(mission: m, busy: busy);
    }
    final near =
        m.status == MissionStatus.enRoute &&
        away != null &&
        away! <= StaffConfig.onSceneRadiusM;
    final caption = m.status == MissionStatus.enRoute && away != null && !near
        ? l10n.staffAwayFrom(away!)
        : null;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        BigStepButton(
          key: Key('step-${next.$1}'),
          label: next.$2,
          caption: caption,
          icon: next.$3,
          tone: next.$4,
          onPressed: busy
              ? null
              : () async {
                  final at = await ref
                      .read(locationServiceProvider)
                      .bestEffort(timeout: const Duration(seconds: 3));
                  await ref
                      .read(staffControllerProvider.notifier)
                      .step(m.id, next.$1, at: at);
                  ref.invalidate(staffPositionProvider);
                },
        ),
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

/// The steps after the arrival (phase S2): one big button for the main one, the other beside it;
/// back at the unit ends the mission. The time is the phone's, kept in order by the server.
class _Milestones extends ConsumerWidget {
  const _Milestones({required this.mission, required this.busy});

  final Mission mission;
  final bool busy;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final steps = mission.nextMilestones;
    if (steps.isEmpty) return const SizedBox.shrink();
    (String, IconData, Tone) look(String step) => switch (step) {
      'left_scene' => (l10n.staffStepLeftScene, Icons.logout, Tone.orange),
      'at_hospital' => (
        l10n.staffStepAtHospital,
        Icons.local_hospital,
        Tone.red,
      ),
      _ => (l10n.staffStepBackAtUnit, Icons.home_work, Tone.green),
    };
    Future<void> give(String step) =>
        ref.read(staffControllerProvider.notifier).milestone(mission.id, step);
    final (label, icon, tone) = look(steps.first);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        BigStepButton(
          key: Key('step-${steps.first}'),
          label: label,
          caption: steps.first == 'back_at_unit'
              ? l10n.staffBackEndsMission
              : null,
          icon: icon,
          tone: tone,
          onPressed: busy ? null : () => give(steps.first),
        ),
        for (final other in steps.skip(1)) ...[
          const SizedBox(height: 8),
          OutlinedButton.icon(
            key: Key('step-$other'),
            style: OutlinedButton.styleFrom(
              minimumSize: const Size.fromHeight(56),
            ),
            onPressed: busy ? null : () => give(other),
            icon: Icon(look(other).$2),
            label: Text(look(other).$1),
          ),
        ],
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
    final loc = mission.location;
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
