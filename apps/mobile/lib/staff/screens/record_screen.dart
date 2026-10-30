import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/ui/components.dart';
import '../../core/ui/tokens.dart';
import '../../l10n/app_localizations.dart';
import '../staff_chrome.dart';
import '../staff_controller.dart';
import '../staff_models.dart';

/// What a mission used, with its step on the steppers (design-system.md `Stepper`): the same list
/// as the room's (services/api/app/modules/ops/record.py `CONSUMABLES`).
const consumableSteps = <String, (int max, int step)>{
  'water_m3': (1000, 1),
  'foam_l': (20000, 10),
  'powder_kg': (5000, 1),
  'co2_kg': (2000, 1),
  'extinguishers': (200, 1),
  'oxygen_l': (50000, 10),
  'fuel_l': (5000, 1),
  'sandbags': (20000, 10),
  'absorbent_kg': (5000, 1),
};

String consumableLabel(AppLocalizations l10n, String key) => switch (key) {
  'water_m3' => l10n.staffUsedWater,
  'foam_l' => l10n.staffUsedFoam,
  'powder_kg' => l10n.staffUsedPowder,
  'co2_kg' => l10n.staffUsedCo2,
  'extinguishers' => l10n.staffUsedExtinguishers,
  'oxygen_l' => l10n.staffUsedOxygen,
  'fuel_l' => l10n.staffUsedFuel,
  'sandbags' => l10n.staffUsedSandbags,
  _ => l10n.staffUsedAbsorbent,
};

/// The crew and the resources of a mission (phase S2, design-s2 §4): counts only, no typing,
/// sent like every other write (kept on the phone without network). The room sees them at once
/// and can correct them.
class MissionRecordScreen extends ConsumerStatefulWidget {
  const MissionRecordScreen({super.key, required this.missionId});

  final String missionId;

  @override
  ConsumerState<MissionRecordScreen> createState() =>
      _MissionRecordScreenState();
}

class _MissionRecordScreenState extends ConsumerState<MissionRecordScreen> {
  final _crew = TextEditingController();
  final _used = {
    for (final k in consumableSteps.keys) k: TextEditingController(),
  };
  bool _filled = false;

  @override
  void dispose() {
    _crew.dispose();
    for (final c in _used.values) {
      c.dispose();
    }
    super.dispose();
  }

  void _fill(Mission m, int? shiftCrew) {
    if (_filled) return;
    _filled = true;
    final crew = m.crewCount ?? shiftCrew;
    _crew.text = crew == null ? '' : '$crew';
    for (final e in _used.entries) {
      final v = m.consumables[e.key];
      e.value.text = v == null || v == 0 ? '' : '$v';
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final s = ref.watch(staffControllerProvider);
    final m = s.mission(widget.missionId);
    if (m == null) {
      return Scaffold(
        appBar: StaffAppBar(title: l10n.staffRecordTitle),
        body: Center(child: Text(l10n.staffMissionGone)),
      );
    }
    _fill(m, s.me?.shift?.crewSize);
    final crew = int.tryParse(_crew.text.trim());
    final ready =
        m.status != MissionStatus.cancelled &&
        crew != null &&
        crew >= 1 &&
        !s.busy;
    return Scaffold(
      appBar: StaffAppBar(
        title: l10n.staffRecordTitle,
        subtitle: s.me?.shift?.vehicle.label,
      ),
      body: Column(
        children: [
          const ConnectionStrip(),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                SectionTitle(l10n.staffRecordCrew),
                NumberStepper(
                  controller: _crew,
                  fieldKey: const ValueKey('record-crew'),
                  label: l10n.staffRecordCrew,
                  min: 1,
                  max: 60,
                  start: 4,
                  onChanged: (_) => setState(() {}),
                ),
                const SizedBox(height: 16),
                SectionTitle(l10n.staffRecordUsed),
                for (final e in consumableSteps.entries) ...[
                  NumberStepper(
                    controller: _used[e.key]!,
                    fieldKey: ValueKey('record-${e.key}'),
                    label: consumableLabel(l10n, e.key),
                    max: e.value.$1,
                    step: e.value.$2,
                    start: e.value.$2,
                    onChanged: (_) => setState(() {}),
                  ),
                  const SizedBox(height: 8),
                ],
              ],
            ),
          ),
        ],
      ),
      bottomNavigationBar: BottomActionBar(
        actions: [
          BarAction(
            key: const Key('send-record'),
            label: l10n.staffRecordSend,
            icon: Icons.send,
            tone: Tone.navy,
            onPressed: ready
                ? () async {
                    final ok = await ref
                        .read(staffControllerProvider.notifier)
                        .teamRecord(
                          m.id,
                          crewCount: crew,
                          consumables: {
                            for (final e in _used.entries)
                              e.key: int.tryParse(e.value.text.trim()) ?? 0,
                          },
                        );
                    if (ok && context.mounted) Navigator.of(context).pop();
                  }
                : null,
          ),
        ],
      ),
    );
  }
}
