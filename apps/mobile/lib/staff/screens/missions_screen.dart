import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/http/models.dart';
import '../../core/settings/settings_controller.dart';
import '../../core/ui/components.dart';
import '../../core/ui/tokens.dart';
import '../../features/report/category_labels.dart';
import '../../l10n/app_localizations.dart';
import '../staff_chrome.dart';
import '../staff_controller.dart';
import '../staff_labels.dart';
import '../staff_models.dart';
import 'mission_screen.dart';

/// Home of a shift: the vehicle, its missions, and the full-screen alert of a new order (F-STF-03).
class MissionsScreen extends ConsumerWidget {
  const MissionsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ringing = ref.watch(staffControllerProvider.select((s) => s.ringing));
    if (ringing != null) return MissionAlert(mission: ringing);
    final l10n = AppLocalizations.of(context);
    final s = ref.watch(staffControllerProvider);
    final c = ref.read(staffControllerProvider.notifier);
    final shift = s.me?.shift;
    final active = [
      for (final m in s.missions)
        if (m.active) m,
    ];
    final done = [
      for (final m in s.missions)
        if (!m.active) m,
    ];
    return Scaffold(
      appBar: StaffAppBar(
        title: shift?.vehicle.label ?? l10n.staffAppTitle,
        subtitle: shift == null
            ? null
            : [
                shift.vehicle.unitName,
                l10n.staffCrewCount(shift.crewSize),
              ].join(' · '),
        actions: [
          PopupMenuButton<String>(
            key: const Key('staff-menu'),
            onSelected: (v) =>
                unawaited(v == 'end' ? _endShift(context, ref) : c.signOut()),
            itemBuilder: (_) => [
              PopupMenuItem(
                key: const Key('end-shift'),
                value: 'end',
                child: Text(l10n.staffEndShift),
              ),
              PopupMenuItem(value: 'out', child: Text(l10n.staffSignOut)),
            ],
          ),
        ],
      ),
      body: Column(
        children: [
          const ConnectionStrip(),
          Expanded(
            child: RefreshIndicator(
              onRefresh: c.poll,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  if (shift != null)
                    NavCard(
                      icon: vehicleKindIcon(shift.vehicle.kind),
                      tone: Tone.green,
                      title: l10n.staffOnShift,
                      subtitle: [
                        shift.vehicle.unitName,
                        l10n.staffCrewCount(shift.crewSize),
                      ].join(' · '),
                    ),
                  const SizedBox(height: 16),
                  SectionTitle(l10n.staffActiveMissions),
                  if (active.isEmpty)
                    AppCard(
                      key: const Key('no-missions'),
                      child: Text(l10n.staffNoMission),
                    ),
                  for (final m in active) _MissionTile(m),
                  if (done.isNotEmpty) ...[
                    const SizedBox(height: 16),
                    SectionTitle(l10n.staffRecentMissions),
                    for (final m in done) _MissionTile(m),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _endShift(BuildContext context, WidgetRef ref) async {
    final l10n = AppLocalizations.of(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l10n.staffEndShift),
        content: Text(l10n.staffEndShiftConfirm),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: Text(l10n.actionCancel),
          ),
          FilledButton(
            key: const Key('end-shift-confirm'),
            onPressed: () => Navigator.pop(context, true),
            child: Text(l10n.staffEndShift),
          ),
        ],
      ),
    );
    if (ok == true) {
      final done = await ref.read(staffControllerProvider.notifier).endShift();
      final error = ref.read(staffControllerProvider).error;
      if (!done && error != null && context.mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(crewErrorLabel(l10n, error))));
      }
    }
  }
}

class _MissionTile extends ConsumerWidget {
  const _MissionTile(this.m);

  final Mission m;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final code = ref.watch(localeCodeProvider);
    final cat = m.category ?? ReportCategory.other;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: NavCard(
        key: Key('mission-${m.id}'),
        icon: categoryIcon(cat),
        tone: missionStatusTone(m.status),
        title: m.title ?? categoryLabel(l10n, cat),
        subtitle: [
          missionStatusLabel(l10n, m.status),
          placeOf(m, code),
        ].where((x) => x.isNotEmpty).join(' · '),
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute<void>(
            builder: (_) => MissionScreen(missionId: m.id),
          ),
        ),
      ),
    );
  }
}

/// New order: covers the whole screen, vibrates, and stays until the leader acknowledges it.
/// (P4a: inside the open app; over the lock screen in P4c.)
class MissionAlert extends ConsumerStatefulWidget {
  const MissionAlert({super.key, required this.mission});

  final Mission mission;

  @override
  ConsumerState<MissionAlert> createState() => _MissionAlertState();
}

class _MissionAlertState extends ConsumerState<MissionAlert> {
  Timer? _buzz;

  @override
  void initState() {
    super.initState();
    unawaited(HapticFeedback.vibrate());
    _buzz = Timer.periodic(
      const Duration(seconds: 2),
      (_) => unawaited(HapticFeedback.vibrate()),
    );
  }

  @override
  void dispose() {
    _buzz?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final code = ref.watch(localeCodeProvider);
    final busy = ref.watch(staffControllerProvider.select((s) => s.busy));
    final m = widget.mission;
    final cat = m.category ?? ReportCategory.other;
    final place = placeOf(m, code);
    return Scaffold(
      key: const Key('mission-alert'),
      body: Column(
        children: [
          Semantics(
            liveRegion: true,
            child: HeroHeader(
              icon: categoryIcon(cat),
              title: l10n.staffNewMission,
              meta: [
                categoryLabel(l10n, cat),
                if (place.isNotEmpty) place,
              ].join(' · '),
            ),
          ),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: [
                if (m.title != null)
                  Text(m.title!, style: Theme.of(context).textTheme.titleLarge),
                if (m.order != null) ...[
                  const SizedBox(height: 12),
                  SectionTitle(l10n.staffOrder),
                  AppCard(child: Text(m.order!)),
                ],
              ],
            ),
          ),
        ],
      ),
      bottomNavigationBar: BottomActionBar(
        actions: [
          BarAction(
            key: const Key('ack-mission'),
            label: l10n.staffAcknowledge,
            icon: Icons.check_circle,
            tone: Tone.red,
            onPressed: busy
                ? null
                : () => unawaited(
                    ref
                        .read(staffControllerProvider.notifier)
                        .acknowledge(m.id),
                  ),
          ),
        ],
      ),
    );
  }
}
