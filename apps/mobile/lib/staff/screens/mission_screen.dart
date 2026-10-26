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
import '../staff_config.dart';
import '../staff_controller.dart';
import '../staff_labels.dart';
import '../staff_models.dart';
import 'casualties_screen.dart';
import 'first_report_screen.dart';

/// One mission: the order, one large button for the next step (F-STF-03), the first report and
/// the casualties (F-STF-04).
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
        appBar: AppBar(actions: staffBarActions()),
        body: Center(child: Text(l10n.staffMissionGone)),
      );
    }
    final code = ref.watch(localeCodeProvider);
    final cat = m.category ?? ReportCategory.other;
    final place = placeOf(m, code);
    return Scaffold(
      appBar: AppBar(
        title: Text(categoryLabel(l10n, cat)),
        actions: staffBarActions(),
      ),
      body: Column(
        children: [
          const OfflineStrip(),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Row(
                  children: [
                    Pill(
                      missionStatusLabel(l10n, m.status),
                      tone: missionStatusTone(m.status),
                    ),
                    const SizedBox(width: 8),
                    if (place.isNotEmpty) Flexible(child: Text(place)),
                  ],
                ),
                if (m.title != null) ...[
                  const SizedBox(height: 12),
                  Text(m.title!, style: Theme.of(context).textTheme.titleLarge),
                ],
                if (m.order != null) ...[
                  const SizedBox(height: 12),
                  SectionTitle(l10n.staffOrder),
                  AppCard(child: Text(m.order!)),
                ],
                if (m.status == MissionStatus.enRoute && m.location != null)
                  _OnSceneHint(mission: m),
                if (s.error != null) ...[
                  const SizedBox(height: 12),
                  Text(
                    crewErrorLabel(l10n, s.error!),
                    key: const Key('staff-error'),
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ],
                const SizedBox(height: 16),
                if (m.status == MissionStatus.onScene ||
                    m.status == MissionStatus.released) ...[
                  NavCard(
                    key: const Key('open-first-report'),
                    icon: Icons.assignment,
                    tone: m.fieldReport == null ? Tone.orange : Tone.green,
                    title: l10n.staffFirstReport,
                    subtitle: m.fieldReport == null
                        ? l10n.staffFirstReportDue
                        : severityLabel(l10n, m.fieldReport!.severity),
                    onTap:
                        m.status == MissionStatus.onScene &&
                            m.fieldReport == null
                        ? () => Navigator.of(context).push(
                            MaterialPageRoute<void>(
                              builder: (_) =>
                                  FirstReportScreen(missionId: m.id),
                            ),
                          )
                        : null,
                  ),
                  const SizedBox(height: 8),
                  NavCard(
                    key: const Key('open-casualties'),
                    icon: Icons.personal_injury,
                    tone: Tone.red,
                    title: l10n.staffCasualties,
                    subtitle: l10n.staffCasualtySummary(
                      m.casualties.injured,
                      m.casualties.deceased,
                      m.transports.length,
                    ),
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => CasualtiesScreen(missionId: m.id),
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
      bottomNavigationBar: _nextStep(context, ref, m, s.busy),
    );
  }

  Widget? _nextStep(BuildContext context, WidgetRef ref, Mission m, bool busy) {
    final l10n = AppLocalizations.of(context);
    final (String status, String label, IconData icon, Tone tone)? next =
        switch (m.status) {
          MissionStatus.ordered => (
            'en_route',
            l10n.staffStepEnRoute,
            Icons.directions_car,
            Tone.orange,
          ),
          MissionStatus.enRoute => (
            'on_scene',
            l10n.staffStepOnScene,
            Icons.place,
            Tone.purple,
          ),
          MissionStatus.onScene => (
            'released',
            l10n.staffStepReleased,
            Icons.flag,
            Tone.green,
          ),
          _ => null,
        };
    if (next == null) return null;
    return BottomActionBar(
      actions: [
        BarAction(
          key: Key('step-${next.$1}'),
          label: next.$2,
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
                },
        ),
      ],
    );
  }
}

/// Close to the incident while still "en route": arriving is suggested (F-STF-03, 150 m).
class _OnSceneHint extends ConsumerWidget {
  const _OnSceneHint({required this.mission});

  final Mission mission;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final here = ref.watch(staffPositionProvider).value;
    if (here == null) return const SizedBox.shrink();
    final d = distanceM(here, mission.location!);
    if (d > StaffConfig.onSceneRadiusM) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: AppCard(
        key: const Key('on-scene-hint'),
        color: Tone.purple.colors(context).tint,
        child: Semantics(
          liveRegion: true,
          child: Text(AppLocalizations.of(context).staffNearScene(d.round())),
        ),
      ),
    );
  }
}
